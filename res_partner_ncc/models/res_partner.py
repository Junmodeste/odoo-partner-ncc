import re
from collections.abc import Iterable

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import SQL
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

# Formats volontairement souples, à confirmer avec la DGI / le greffe (voir README).
# NCC : 7 à 9 chiffres, éventuellement suivis d'une lettre clé (ex. 1234567A).
NCC_PATTERN = re.compile(r"^\d{7,9}[A-Z]?$")
# RCCM : commence par CI, puis lettres, chiffres et tirets (ex. CI-ABJ-2017-B-12345).
RCCM_PATTERN = re.compile(r"^CI[A-Z0-9-]{6,30}$")

NCC_KEY = "CI_NCC"
RCCM_KEY = "CI_RCCM"


def normalize_identifier(value):
    """Majuscules, sans espaces. Renvoie False pour une valeur vide."""
    if not value:
        return False
    return re.sub(r"\s+", "", value).upper() or False


def _validator(pattern):
    """Fonction de validation au format attendu par Odoo 20 : renvoie la valeur normalisée, lève sinon."""
    def validate(value):
        value = normalize_identifier(value)
        if not value or not pattern.match(value):
            raise ValueError(value)
        return value
    return validate


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Odoo 20 : NCC et RCCM sont stockés dans `additional_identifiers` (JSON) ;
    # ces champs en sont une vue lisible, modifiable et cherchable.
    ncc = fields.Char(
        string="NCC", compute="_compute_ncc_rccm", inverse="_inverse_ncc", search="_search_ncc",
        help="Taxpayer account number (Numéro de compte contribuable, DGI).",
    )
    rccm = fields.Char(
        string="RCCM", compute="_compute_ncc_rccm", inverse="_inverse_rccm", search="_search_rccm",
        help="Trade and personal property credit register (RCCM).",
    )

    @api.model
    def _get_all_additional_identifiers_metadata(self):
        # Sans `category` : Odoo 20 ne les imprime pas lui-même comme identifiant fiscal / légal
        # préféré de la facture (« Tax ID : … »), le bloc du module s'en charge (libellés NCC / RCCM).
        return {
            **super()._get_all_additional_identifiers_metadata(),
            NCC_KEY: {
                "sequence": 10,
                "label": _lt("NCC"),
                "help": _lt("Taxpayer account number (Numéro de compte contribuable, DGI)."),
                "placeholder": "1234567A",
                "validation_function": _validator(NCC_PATTERN),
                "countries": ["CI"],
            },
            RCCM_KEY: {
                "sequence": 20,
                "label": _lt("RCCM"),
                "help": _lt("Trade and personal property credit register (RCCM)."),
                "placeholder": "CI-ABJ-2017-B-12345",
                "validation_function": _validator(RCCM_PATTERN),
                "countries": ["CI"],
            },
        }

    # Normaliser aussi à l'écriture : sinon le cache garde la valeur saisie brute jusqu'au prochain calcul.
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

    @api.depends("additional_identifiers")
    def _compute_ncc_rccm(self):
        for partner in self:
            partner.ncc = partner._get_additional_identifier(NCC_KEY) or False
            partner.rccm = partner._get_additional_identifier(RCCM_KEY) or False

    def _inverse_ncc(self):
        for partner in self:
            partner._set_additional_identifier(NCC_KEY, normalize_identifier(partner.ncc))

    def _inverse_rccm(self):
        for partner in self:
            partner._set_additional_identifier(RCCM_KEY, normalize_identifier(partner.rccm))

    @api.model
    def _search_identifier(self, key, operator, value):
        """Recherche dans le JSON : =, !=, in, not in, like, ilike (et leurs négations)."""
        negative = operator in ("!=", "not in", "not like", "not ilike")
        expr = SQL("additional_identifiers ->> %s", key)
        if operator in ("=", "!=", "in", "not in"):
            values = [v for v in (value if isinstance(value, Iterable) and not isinstance(value, str) else [value]) if v]
            if not values:  # recherche « vide » : (ncc, '=', False)
                return [("id", "in" if negative else "not in", self._ids_where(SQL("%s IS NOT NULL", expr)))]
            condition = SQL("%s IN %s", expr, tuple(normalize_identifier(v) for v in values))
        elif operator in ("like", "ilike", "not like", "not ilike"):
            op = SQL("ILIKE") if "ilike" in operator else SQL("LIKE")
            condition = SQL("%s %s %s", expr, op, f"%{value or ''}%")
        else:
            raise NotImplementedError(f"Operator {operator!r} is not supported on {key}")
        return [("id", "not in" if negative else "in", self._ids_where(condition))]

    @api.model
    def _ids_where(self, condition):
        self.env.flush_all()
        self.env.cr.execute(SQL("SELECT id FROM res_partner WHERE %s", condition))
        return [row[0] for row in self.env.cr.fetchall()]

    @api.constrains("additional_identifiers", "company_id")
    def _check_ncc_unique(self):
        """Un même NCC une seule fois par société Odoo (les contacts partagés comptent comme société 0)."""
        self.env["res.partner"].flush_model(["additional_identifiers", "company_id"])
        self.env.cr.execute(SQL(
            """
            SELECT 1 FROM res_partner a
              JOIN res_partner b ON b.id <> a.id
               AND b.additional_identifiers ->> %(key)s = a.additional_identifiers ->> %(key)s
               AND COALESCE(b.company_id, 0) = COALESCE(a.company_id, 0)
               AND b.commercial_partner_id <> a.commercial_partner_id
             WHERE a.id IN %(ids)s LIMIT 1
            """,
            key=NCC_KEY, ids=tuple(self.ids) or (0,),
        ))
        if self.env.cr.fetchone():
            raise ValidationError(self.env._("This NCC is already used by another contact."))

    @api.model
    def _search_ncc(self, operator, value):
        return self._search_identifier(NCC_KEY, operator, value)

    @api.model
    def _search_rccm(self, operator, value):
        return self._search_identifier(RCCM_KEY, operator, value)
