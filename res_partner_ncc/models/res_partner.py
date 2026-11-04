import re

from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError

# Formats volontairement souples, à confirmer avec la DGI / le greffe (voir README).
# NCC : 7 à 9 chiffres, éventuellement suivis d'une lettre clé (ex. 1234567A).
NCC_PATTERN = re.compile(r"^\d{7,9}[A-Z]?$")
# RCCM : commence par CI, puis lettres, chiffres et tirets (ex. CI-ABJ-2017-B-12345).
RCCM_PATTERN = re.compile(r"^CI[A-Z0-9-]{6,30}$")


def normalize_identifier(value):
    """Majuscules, sans espaces. Renvoie False pour une valeur vide."""
    if not value:
        return False
    return re.sub(r"\s+", "", value).upper() or False


class ResPartner(models.Model):
    _inherit = "res.partner"

    ncc = fields.Char(string="NCC", index="btree_not_null", copy=False, help="Taxpayer account number (Numéro de compte contribuable, DGI).")
    rccm = fields.Char(string="RCCM", copy=False, help="Trade and personal property credit register (RCCM).")

    def init(self):
        super().init()
        # Un même NCC une seule fois par société Odoo (les contacts partagés comptent comme société 0).
        # Index unique plutôt que _sql_constraints (pas d'expression COALESCE) ; un NCC vide (NULL) n'entre jamais en conflit.
        tools.create_unique_index(
            self.env.cr, "res_partner_ncc_company_uniq", self._table, ["ncc", "COALESCE(company_id, 0)"]
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_ncc_rccm(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_ncc_rccm(vals)
        return super().write(vals)

    @api.model
    def _normalize_ncc_rccm(self, vals):
        for fname in ("ncc", "rccm"):
            if fname in vals:
                vals[fname] = normalize_identifier(vals[fname])

    @api.constrains("ncc", "rccm")
    def _check_ncc_rccm_format(self):
        for partner in self:
            if partner.ncc and not NCC_PATTERN.match(partner.ncc):
                raise ValidationError(_(
                    "Invalid NCC “%(ncc)s”: expected 7 to 9 digits, optionally followed by a letter (e.g. 1234567A).",
                    ncc=partner.ncc,
                ))
            if partner.rccm and not RCCM_PATTERN.match(partner.rccm):
                raise ValidationError(_(
                    "Invalid RCCM “%(rccm)s”: expected to start with CI (e.g. CI-ABJ-2017-B-12345).",
                    rccm=partner.rccm,
                ))
