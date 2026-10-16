"""TangTang V5 companion brain.

The brain decides whether an interaction needs attention and what behavior is
appropriate. It does not speak, call an LLM, access devices, or mutate memory.
""" 
from core.brain.planner import CompanionPlan, CompanionPlanner

__all__ = ["CompanionPlan", "CompanionPlanner"]
