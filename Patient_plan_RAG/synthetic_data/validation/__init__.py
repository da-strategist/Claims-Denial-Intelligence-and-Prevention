"""Validation set: synthetic plans and questions kept apart from the
regression eval (synthetic_data/scenarios), and never used to tune the app.

    python -m synthetic_data.validation.generate     # write data/validation/*.pdf
    python -m synthetic_data.validation.review_sheet # write REVIEW_SHEET.md
    python -m backend.app.tests.validation_eval      # score against the pass marks
"""
