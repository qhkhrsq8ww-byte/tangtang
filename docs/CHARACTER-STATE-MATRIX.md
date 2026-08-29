# Character State Matrix

| Event | Context | Policy | State | Speech |
|------|------|------|------|------|
| home.arrived | child | SPEAK | welcome | yes |
| conversation.started | emotion=sad | SPEAK | caring | yes |
| conversation.started | intent=question | SPEAK | curious | yes |
| conversation.started | neutral | SPEAK | talk | yes |
| conversation.started | emotion=happy | SPEAK | happy | yes |
| screen.usage | low | SPEAK | encouraging | yes |
| exercise.started | companion | SPEAK | running | yes |
| exercise.started | reminder | SPEAK | encouraging | yes |
| homework | quiet | SPEAK | accompany | yes |
| homework | question | SPEAK | thinking | yes |
| homework | refuse | SPEAK | encouraging | yes |
| sleep.started | - | SILENT | sleeping | no |
| exercise.started | 23:30 | SILENT | night | no |
| night | - | SILENT | night | no |
