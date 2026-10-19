"""Synthetic policy specs. Every insurer and plan here is fictional."""

from . import apex_gold_ppo, northwind_bronze_hdhp, riverbend_medicaid, summit_silver_hmo

POLICIES = [
    apex_gold_ppo.POLICY,
    summit_silver_hmo.POLICY,
    northwind_bronze_hdhp.POLICY,
    riverbend_medicaid.POLICY,
]
