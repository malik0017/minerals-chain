"""
app/services/master_data — Batch I generic master-data engine.

  registry.py      — declarative description of every master entity
                     (fields, types, FK targets, list columns, natural key)
  service.py       — generic list / get / save / toggle / delete /
                     CSV export / CSV import, all driven by the registry
  starter_data.py  — reference data from Minerals_ERP_Master_Data.pdf
                     and Saudi reference lists, loaded through the same
                     import path (so loading it also exercises import)
  batch_service.py — QC evaluation: spec → result → PASS/FAIL → release

Adding a new master = one model + one Entity(...) entry in registry.py.
No new route, template or form code is needed — that is what makes
"admin manages everything from the frontend" sustainable.
"""
