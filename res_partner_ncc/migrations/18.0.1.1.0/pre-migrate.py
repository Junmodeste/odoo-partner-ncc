def migrate(cr, version):
    # 18.0.1.0.0 created a plain unique index with the same name; the EXCLUDE constraint replaces it.
    cr.execute("DROP INDEX IF EXISTS res_partner_ncc_company_uniq")
