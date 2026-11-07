from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Stockés sur le partenaire de la société : format et unicité s'appliquent.
    ncc = fields.Char(related="partner_id.ncc", readonly=False)
    rccm = fields.Char(related="partner_id.rccm", readonly=False)

    # Normaliser ici aussi, sinon le cache de la société garde la valeur saisie brute.
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self.env["res.partner"]._normalize_ncc_rccm(vals)
        return super().create(vals_list)

    def write(self, vals):
        self.env["res.partner"]._normalize_ncc_rccm(vals)
        return super().write(vals)
