def migrate(cr, version):
    """NCC / RCCM : de colonnes dédiées vers `additional_identifiers` (JSON natif d'Odoo 20)."""
    cr.execute("""
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'res_partner' AND column_name IN ('ncc', 'rccm')
    """)
    columns = {row[0] for row in cr.fetchall()}
    if not columns:
        return
    for column, key in (("ncc", "CI_NCC"), ("rccm", "CI_RCCM")):
        if column in columns:
            cr.execute(
                f"""
                UPDATE res_partner
                   SET additional_identifiers = COALESCE(additional_identifiers, '{{}}'::jsonb)
                                                || jsonb_build_object(%s, {column})
                 WHERE {column} IS NOT NULL
                """,
                [key],
            )
    # Supprimer une colonne supprime aussi l'index unique du NCC qui en dépend.
    cr.execute("ALTER TABLE res_partner " + ", ".join(f"DROP COLUMN {c}" for c in sorted(columns)))
