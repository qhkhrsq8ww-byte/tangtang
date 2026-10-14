"""Wrap V3 cat-chat. New path cannot skip PrivacyPolicy.

V3 cat-chat.py still exists for helpers (looks_risky / sanitize / urllib).
CLI default is TangTangRuntime; opt-out / fail path uses this adapter so LLM
only sees PrivacyPolicy-filtered context. Adapter path:

  STT text → Voice Observation → Identity → Event → PrivacyPolicy
  → Memory → ContextBuilder → LLM (optional) → ResponseOrchestrator → TTSAdapter

LLM only sees PrivacyPolicy-filtered context. It does not call TTS,
projection, shell, or files.
"""
from __future__ import annotations

import importlib.util
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.adapters.family_loader import load_members
from core.ingest import IngestResult, PrivacyPipeline
from core.memory.explicit_intents import MemoryIntent, category_text, parse_memory_intent
from core.memory.recall import retrieve_structured_memories
from core.tasks.intents import TaskIntent, parse_task_intent
from core.tasks.reminders import ReminderIntent, parse_reminder_intent
from core.tasks.service import TaskService
from core.policy.injection import InjectionGuard
from core.policy.speak_gate import decide as speak_decide, may_call_llm
from core.response.orchestrator import PresentationAction
from core.runtime.isolate import isolate

_CAT_CHAT = Path(__file__).resolve().parents[2] / "code" / "cat" / "cat-chat.py"

LLMFn = Callable[[Mapping[str, Any]], str]
LLM_FALLBACK = "糖糖在呢，刚刚没接上。"


def _load_cat_chat_helpers() -> tuple[Callable[[str], bool] | None, Callable[[str], str] | None]:
    """Reuse looks_risky / sanitize_output. Do not call V3 chat() (unfiltered prompt)."""
    if not _CAT_CHAT.is_file():
        return None, None
    spec = importlib.util.spec_from_file_location("tangtang_v3_chat", _CAT_CHAT)
    if spec is None or spec.loader is None:
        return None, None
    mod = importlib.util.module_from_spec(spec)
    loaded = isolate(lambda: spec.loader.exec_module(mod))  # type: ignore[union-attr]
    if not loaded.ok:
        return None, None
    risky = getattr(mod, "looks_risky", None)
    sanitize = getattr(mod, "sanitize_output", None)
    return (risky if callable(risky) else None, sanitize if callable(sanitize) else None)


def _filtered_prompt(context: Mapping[str, Any]) -> str:
    """User-facing prompt from already-filtered context. No extra family dumps."""
    utterance = str(context.get("utterance") or "")
    who = context.get("who") if isinstance(context.get("who"), Mapping) else {}
    member_id = who.get("member_id") if isinstance(who, Mapping) else None
    scope = context.get("privacy_scope") or "PRIVATE"
    family = context.get("family") if isinstance(context.get("family"), Mapping) else {}
    # Family snapshot must already be structured / non-PRIVATE. No raw history.
    family_bits = []
    for key in ("mood", "interaction_count", "summary"):
        if key in family and family[key] not in (None, ""):
            family_bits.append(f"{key}={family[key]}")
    parts = [
        f"member={member_id or 'unknown'}",
        f"privacy={scope}",
    ]
    if family_bits:
        parts.append("family[" + ",".join(str(b) for b in family_bits) + "]")
    # Only explicitly allowlisted structured facts may enter the prompt; never raw turn history.
    recall = context.get("recall")
    if isinstance(recall, list):
        rendered = []
        for row in recall[:5]:
            if not isinstance(row, Mapping):
                continue
            data = row.get("data") if isinstance(row.get("data"), Mapping) else {}
            facts = [f"{key}={str(value)[:180]}" for key, value in data.items() if value not in (None, "")]
            if facts:
                rendered.append(f"{row.get('type', 'memory')}:" + ",".join(facts))
        if rendered:
            parts.append("authorized_memory[" + ";".join(rendered)[:700] + "]")
    parts.append("utterance=" + utterance)
    return "\n".join(parts)


def _llm_payload(context: Mapping[str, Any], utterance: str, who: Mapping[str, Any], scope: str) -> dict[str, Any]:
    """Slim dict; includes only the allowlisted structured-memory projection, never raw history."""
    return {
        "_filtered_prompt": _filtered_prompt(context),
        "utterance": utterance,
        "who": dict(who),
        "privacy_scope": scope,
        "scene": context.get("scene"),
    }


@dataclass
class ChatTurn:
    action: PresentationAction
    ingest: IngestResult
    context: dict[str, Any] = field(default_factory=dict)


class ChatAdapter:
    """Speech → PrivacyPipeline. Optional LLM sees filtered context only."""

    core_api_version = "4.0.0"

    def __init__(
        self,
        pipeline: PrivacyPipeline | None = None,
        *,
        members: Mapping[str, object] | None = None,
        llm: LLMFn | None = None,
        allow_private_llm: bool = False,
        allow_unknown_llm: bool = False,
        tasks: TaskService | None = None,
        sanitize: Callable[[str], str] | None = None,
        looks_risky: Callable[[str], bool] | None = None,
    ) -> None:
        roster = dict(members) if members is not None else load_members()
        self.pipeline = pipeline or PrivacyPipeline(members=roster)
        self._llm = llm
        self._allow_private_llm = bool(allow_private_llm)
        self._allow_unknown_llm = bool(allow_unknown_llm)
        self.tasks = tasks or TaskService(members=roster)
        risky, sanit = _load_cat_chat_helpers()
        self._sanitize = sanitize or sanit
        self._looks_risky = looks_risky or risky
        self._injection = InjectionGuard()

    def turn(
        self,
        utterance: str,
        observation: Mapping[str, Any] | None = None,
        *,
        viewer_id: str | None = None,
    ) -> ChatTurn:
        """New path. PrivacyPolicy runs inside ingest before Event / Memory / LLM."""
        obs = dict(observation or {})
        obs.setdefault("interactive", True)
        text = utterance or str(obs.get("utterance") or obs.get("speech") or "")
        risk_detected = False
        if self._looks_risky is not None:
            risky = isolate(lambda: bool(self._looks_risky(text)), fallback=False)
            if risky.ok and risky.value:
                risk_detected = True
                obs = {**obs, "safety": "risk"}
        # These explicit commands retain only the structured result, not the original utterance.
        memory_intent = None if risk_detected else parse_memory_intent(text)
        reminder_now = obs.get("now") if isinstance(obs.get("now"), datetime) else None
        reminder_intent = None if risk_detected else parse_reminder_intent(
            text, now=reminder_now, timezone_name=obs.get("timezone")
        )
        task_intent = None if risk_detected else parse_task_intent(text)
        ingested = self.pipeline.ingest(
            text,
            obs,
            store_private_memory=memory_intent is None and reminder_intent is None and task_intent is None,
        )
        speaker_id = ingested.decision.member_id
        effective_viewer_id = viewer_id or speaker_id
        who = {"member_id": speaker_id}
        if memory_intent is not None:
            local_result = self._handle_memory_intent(
                intent=memory_intent,
                ingested=ingested,
                member_id=speaker_id,
                viewer_id=effective_viewer_id,
            )
            if local_result is not None:
                return local_result
        if reminder_intent is not None:
            local_result = self._handle_reminder_intent(
                intent=reminder_intent,
                ingested=ingested,
                member_id=speaker_id,
                viewer_id=effective_viewer_id,
            )
            if local_result is not None:
                return local_result
        if task_intent is not None:
            local_result = self._handle_task_intent(
                intent=task_intent,
                ingested=ingested,
                member_id=speaker_id,
                viewer_id=effective_viewer_id,
            )
            if local_result is not None:
                return local_result
        now = obs.get("now")
        when = now if isinstance(now, datetime) else None
        decision = speak_decide(
            obs,
            now=when,
            channel="chat",
            policy=self.pipeline.interrupt,
            live=bool(obs.get("live")),
        )
        if not may_call_llm(decision):
            ctx = {
                "who": who,
                "utterance": text,
                "policy_decision": decision,
                "privacy_scope": ingested.decision.privacy,
            }
            return ChatTurn(
                action=self.pipeline.orchestrator.run(
                    decision=decision, context=ctx, action="idle"
                ),
                ingest=ingested,
                context=ctx,
            )
        if self._injection.is_injection(text):
            ctx = {
                "who": who,
                "current_event": ingested.event.to_dict(),
                "memory": [],
                "family": {},
                "utterance": text,
                "injection": True,
                "private_facts": [],
            }
            return ChatTurn(
                action=self.pipeline.orchestrator.run(decision="SPEAK", context=ctx, action="refuse"),
                ingest=ingested,
                context=ctx,
            )
        scope = ingested.decision.privacy
        family_snapshot: dict[str, Any] = {}
        if ingested.decision.allow_family_summary:
            snap = isolate(lambda: self.pipeline.stores.summary.snapshot())
            if snap.ok and isinstance(snap.value, list):
                family_snapshot = {"members": snap.value}
        ctx = self.pipeline.builder.build(
            who=who,
            event=ingested.event,
            observation={**obs, "utterance": text},
            family=family_snapshot,
            privacy_scope=scope,
            viewer_id=effective_viewer_id,
        )
        ctx["utterance"] = text
        ctx["scene"] = obs.get("scene")
        ctx["event_id"] = ingested.event.id
        recall = isolate(
            lambda: retrieve_structured_memories(
                member_id=speaker_id,
                viewer_id=effective_viewer_id,
                privacy_scope=scope,
                private_store=self.pipeline.stores.private,
                family_store=self.pipeline.stores.family,
            ),
            fallback=[],
        )
        ctx["recall"] = recall.value if recall.ok and isinstance(recall.value, list) else []
        # PRIVATE is local-first: never send it to a model gateway without an explicit opt-in.
        # When blocked, fall through to PersonaRenderer instead of returning a generic error.
        private_cloud_blocked = scope == "PRIVATE" and not self._allow_private_llm
        # Unknown identity is not consent to upload speech. Stay local unless the household explicitly opts in.
        unknown_cloud_blocked = ingested.decision.member_id is None and not self._allow_unknown_llm
        if (
            self._llm is not None
            and may_call_llm(decision)
            and not private_cloud_blocked
            and not unknown_cloud_blocked
        ):
            ctx["skip_persona"] = True
            prompt_ctx = _llm_payload(ctx, text, who, scope)

            def _call_llm() -> str:
                return str(self._llm(prompt_ctx))

            llm_res = isolate(_call_llm, fallback=LLM_FALLBACK)
            text_out = llm_res.value if llm_res.ok and isinstance(llm_res.value, str) else LLM_FALLBACK
            if not text_out.strip():
                text_out = LLM_FALLBACK
            if self._sanitize is not None:
                cleaned = isolate(lambda: self._sanitize(text_out), fallback=text_out)
                if cleaned.ok and isinstance(cleaned.value, str) and cleaned.value.strip():
                    text_out = cleaned.value
            ctx["llm_text"] = text_out
            original = self.pipeline.orchestrator.responder
            self.pipeline.orchestrator.responder = lambda _c, t=text_out: t
            try:
                action = self.pipeline.orchestrator.run(decision=decision, context=ctx, action="reply")
            finally:
                self.pipeline.orchestrator.responder = original
            return ChatTurn(action=action, ingest=ingested, context=ctx)
        action = self.pipeline.orchestrator.run(decision=decision, context=ctx, action="reply")
        return ChatTurn(action=action, ingest=ingested, context=ctx)

    def _handle_reminder_intent(
        self,
        *,
        intent: ReminderIntent,
        ingested: IngestResult,
        member_id: str | None,
        viewer_id: str | None,
    ) -> ChatTurn | None:
        """Create, clarify and schedule reminders locally; never claim delivery before dispatch."""
        if not member_id:
            return None
        if viewer_id != member_id:
            text = "我还不能确认这是你的提醒，先不创建或修改。"
            operation = "reminder_denied"
        elif intent.action == "list":
            rows = self.tasks.list_tasks(
                viewer_id=member_id,
                statuses={"needs_confirmation", "scheduled", "running", "failed"},
                include_family=False,
                limit=20,
            )
            rows = [task for task in rows if task.kind == "reminder"]
            if not rows:
                text = "你现在没有待处理的提醒。"
            else:
                text = "你的提醒有：" + "；".join(
                    f"{task.title}（{'待补时间' if not task.due_at else task.due_at}，{task.status}）"
                    for task in rows[:8]
                ) + "。"
            operation = "reminder_list"
        elif intent.action in {"cancel", "reschedule"}:
            candidates = self.tasks.list_tasks(
                viewer_id=member_id,
                statuses={"needs_confirmation", "scheduled", "failed"},
                include_family=False,
                limit=500,
            )
            candidates = [
                task for task in candidates
                if task.kind == "reminder"
                and self._normalize_task_title(task.title) == self._normalize_task_title(intent.title or "")
            ]
            if len(candidates) != 1:
                text = (
                    "我没找到名称完全相同的提醒，或有多个同名提醒。你可以先说“查看提醒”，再用完整事项名称操作。"
                )
                operation = "reminder_not_found"
            elif intent.action == "cancel":
                task = self.tasks.cancel(candidates[0].task_id, owner_member_id=member_id)
                text = f"好，已经取消提醒：{task.title}。"
                operation = "reminder_cancel"
            elif not intent.due_at:
                text = "我没识别出新的提醒时间。请说清楚日期和几点，例如“把带水杯提醒改到明天晚上八点”。"
                operation = "reminder_clarify"
            else:
                task = self.tasks.reschedule(
                    candidates[0].task_id,
                    owner_member_id=member_id,
                    due_at=intent.due_at,
                    timezone_name=intent.timezone_name,
                )
                text = f"好，已经修改提醒：{task.title}，新时间是 {task.due_at}。"
                operation = "reminder_reschedule"
        elif intent.action == "time_reply":
            pending = self.tasks.list_tasks(
                viewer_id=member_id,
                statuses={"needs_confirmation"},
                include_family=False,
                limit=20,
            )
            pending = [task for task in pending if task.kind == "reminder"]
            if len(pending) != 1 or not intent.due_at:
                return None
            task = self.tasks.reschedule(
                pending[0].task_id,
                owner_member_id=member_id,
                due_at=intent.due_at,
                timezone_name=intent.timezone_name,
            )
            text = f"好，已经设置提醒：{task.title}，时间是 {task.due_at}。到时我会尝试播放提醒。"
            operation = "reminder_schedule"
        elif intent.action == "needs_details":
            text = "我可以提醒你。先告诉我具体要提醒什么，再告诉我哪一天、几点。"
            operation = "reminder_clarify"
        elif intent.action == "needs_time":
            if not intent.title:
                text = "你想让我提醒什么事情？告诉我事项和时间就行。"
                operation = "reminder_clarify"
            else:
                task = self.tasks.create_task(
                    owner_member_id=member_id,
                    title=intent.title,
                    kind="reminder",
                    visibility="PRIVATE",
                    status="needs_confirmation",
                    source_event_id=ingested.event.id,
                    idempotency_key=f"reminder-draft:{ingested.event.id}",
                    timezone_name=intent.timezone_name or "UTC",
                )
                text = f"我记下要提醒你：{task.title}。还没设置成功哦，你想让我哪天几点提醒？"
                operation = "reminder_needs_time"
        elif intent.action == "schedule" and intent.title and intent.due_at:
            task = self.tasks.create_task(
                owner_member_id=member_id,
                title=intent.title,
                due_at=intent.due_at,
                timezone_name=intent.timezone_name or "UTC",
                kind="reminder",
                visibility="PRIVATE",
                status="scheduled",
                source_event_id=ingested.event.id,
                idempotency_key=f"reminder-event:{ingested.event.id}",
            )
            text = f"好，已经设置提醒：{task.title}，时间是 {task.due_at}。到时我会尝试播放提醒。"
            operation = "reminder_schedule"
        else:
            return None
        context = {
            "who": {"member_id": member_id},
            "current_event": ingested.event.to_dict(),
            "privacy_scope": "PRIVATE",
            "task_operation": operation,
            "private_facts": [],
        }
        if self._sanitize is not None:
            cleaned = isolate(lambda: self._sanitize(text), fallback=text)
            if cleaned.ok and isinstance(cleaned.value, str) and cleaned.value.strip():
                text = cleaned.value
        action = PresentationAction(
            decision="SPEAK",
            text=text,
            action=operation,
            member_id=member_id,
            sink="voice",
            private_facts=(),
        )
        return ChatTurn(action=action, ingest=ingested, context=context)

    def _handle_task_intent(
        self,
        *,
        intent: TaskIntent,
        ingested: IngestResult,
        member_id: str | None,
        viewer_id: str | None,
    ) -> ChatTurn | None:
        """Handle explicit todos locally. Existing alarm scheduling stays in cat-alarm.py."""
        if not member_id:
            return None
        if viewer_id != member_id:
            text = "我还不能确认这是你的待办清单，先不读取或修改。"
            visible_tasks = []
        else:
            visible_tasks = []
            active = {"proposed", "needs_confirmation", "scheduled", "running", "failed"}
            if intent.action == "create" and intent.title:
                try:
                    task = self.tasks.create_task(
                        owner_member_id=member_id,
                        title=intent.title,
                        kind="task",
                        visibility="PRIVATE",
                        status="proposed",
                        source_event_id=ingested.event.id,
                        idempotency_key=f"todo-event:{ingested.event.id}",
                    )
                    visible_tasks = [{
                        "title": task.title,
                        "status": task.status,
                        "due_at": task.due_at,
                    }]
                    text = f"好，记下来了：{task.title}。目前还没有设置提醒时间。"
                except (ValueError, PermissionError):
                    text = "这件待办我没能保存下来，咱们换个简短一点的说法再试试。"
            elif intent.action == "list":
                visible_tasks = [
                    {
                        "title": task.title,
                        "status": task.status,
                        "due_at": task.due_at,
                    }
                    for task in self.tasks.list_tasks(
                        viewer_id=member_id,
                        statuses=active,
                        include_family=False,
                        limit=10,
                    )
                ]
                if not visible_tasks:
                    text = "你现在没有待办事项。"
                else:
                    titles = [str(row["title"])[:60] for row in visible_tasks[:5]]
                    text = f"你现在有 {len(visible_tasks)} 件待办：" + "；".join(titles) + "。"
                    if len(visible_tasks) > 5:
                        text += "还有几件，咱们可以接着看。"
            elif intent.action in {"complete", "cancel"} and intent.title:
                wanted = self._normalize_task_title(intent.title)
                candidates = self.tasks.list_tasks(
                    viewer_id=member_id,
                    statuses=active,
                    include_family=False,
                    limit=500,
                )
                matches = [
                    task for task in candidates
                    if self._normalize_task_title(task.title) == wanted
                ]
                if len(matches) > 1:
                    text = "有几件待办名称相同，先告诉我更完整的事项名称，我再处理。"
                elif not matches:
                    text = "我没找到名称完全相同的待办，你可以说“完成待办：事项名称”。"
                elif intent.action == "complete":
                    task = self.tasks.complete(
                        matches[0].task_id,
                        owner_member_id=member_id,
                        result="completed_by_user",
                    )
                    text = f"好，这件待办已经标记完成：{task.title}。"
                else:
                    task = self.tasks.cancel(matches[0].task_id, owner_member_id=member_id)
                    text = f"好，这件待办已经取消：{task.title}。"
            else:
                return None
        context = {
            "who": {"member_id": member_id},
            "current_event": ingested.event.to_dict(),
            "privacy_scope": "PRIVATE",
            "task_operation": intent.action,
            "tasks": visible_tasks,
            "private_facts": [],
        }
        if self._sanitize is not None:
            cleaned = isolate(lambda: self._sanitize(text), fallback=text)
            if cleaned.ok and isinstance(cleaned.value, str) and cleaned.value.strip():
                text = cleaned.value
        action = PresentationAction(
            decision="SPEAK",
            text=text,
            action=f"task_{intent.action}",
            member_id=member_id,
            sink="voice",
            private_facts=(),
        )
        return ChatTurn(action=action, ingest=ingested, context=context)

    @staticmethod
    def _normalize_task_title(title: str) -> str:
        return " ".join(str(title or "").strip().strip(" ，,。.!！?？:：").split()).casefold()

    def _handle_memory_intent(
        self,
        *,
        intent: MemoryIntent,
        ingested: IngestResult,
        member_id: str | None,
        viewer_id: str | None,
    ) -> ChatTurn | None:
        """Handle explicit remember/forget/recall commands locally, never via LLM."""
        if not member_id:
            return None
        if viewer_id != member_id:
            text = "我还不能确认这是你的个人记忆，先不读取或修改。"
            rows: list[dict[str, Any]] = []
        else:
            rows = []
            if intent.action == "remember" and intent.category and intent.value:
                memory = self.pipeline.stores.private.remember_preference(
                    member_id=member_id,
                    category=intent.category,
                    value=intent.value,
                    event_id=ingested.event.id,
                )
                text = f"好，我记住了：你{category_text(intent.category)}「{memory.data['value']}」。"
                rows = [ {
                    "type": "preference",
                    "privacy": "PRIVATE",
                    "data": dict(memory.data),
                    "created_at": memory.created_at or "",
                } ]
            elif intent.action == "forget" and intent.category and intent.value:
                removed = self.pipeline.stores.private.forget_preference(
                    member_id=member_id,
                    category=intent.category,
                    value=intent.value,
                )
                text = "好，我把这条偏好忘掉了。" if removed else "我没找到这条偏好，可能还没记住。"
            elif intent.action == "recall":
                for row in self.pipeline.stores.private.query(
                    member_id=member_id, viewer_id=viewer_id
                ):
                    data = row.get("data") if isinstance(row.get("data"), Mapping) else {}
                    if row.get("type") != "preference" or not isinstance(data.get("value"), str):
                        continue
                    if intent.category and data.get("tag") != intent.category:
                        continue
                    if set(data.keys()) != {"tag", "value"}:
                        continue
                    rows.append({
                        "type": "preference",
                        "privacy": "PRIVATE",
                        "data": {"tag": data["tag"], "value": data["value"]},
                        "created_at": row.get("created_at") or "",
                    })
                rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
                rows = rows[:3]
                if not rows:
                    text = "我还没记住这类偏好。你可以明确告诉我想让我记住什么。"
                else:
                    snippets = [
                        f"你{category_text(str(row['data']['tag']))}「{row['data']['value']}」"
                        for row in rows
                    ]
                    text = "我记得，" + "，还有".join(snippets) + "。"
            else:
                return None
        context = {
            "who": {"member_id": member_id},
            "current_event": ingested.event.to_dict(),
            "privacy_scope": "PRIVATE",
            "memory_operation": intent.action,
            "recall": rows,
            "private_facts": [],
        }
        action = PresentationAction(
            decision="SPEAK",
            text=text,
            action=f"memory_{intent.action}",
            member_id=member_id,
            sink="voice",
            private_facts=(),
        )
        return ChatTurn(action=action, ingest=ingested, context=context)

    def reply(
        self,
        utterance: str,
        observation: Mapping[str, Any] | None = None,
        *,
        viewer_id: str | None = None,
    ) -> PresentationAction:
        return self.turn(utterance, observation, viewer_id=viewer_id).action
