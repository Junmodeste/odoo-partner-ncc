from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestResPartnerNcc(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.customer = cls.Partner.create({"name": "Client SARL", "is_company": True})

    def test_normalization(self):
        self.customer.write({"ncc": " 1234567 a ", "rccm": "ci-abj-2017-b-12345"})
        self.assertEqual(self.customer.ncc, "1234567A")
        self.assertEqual(self.customer.rccm, "CI-ABJ-2017-B-12345")
        partner = self.Partner.create({"name": "Autre SA", "is_company": True, "ncc": "  "})
        self.assertFalse(partner.ncc)

    def test_invalid_format(self):
        with self.assertRaises(ValidationError):
            self.customer.ncc = "ABC"
        with self.assertRaises(ValidationError):
            self.customer.rccm = "ABJ-2017-B-12345"

    def test_ncc_unique_per_company(self):
        self.customer.ncc = "1234567A"
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.cr.savepoint():
            self.Partner.create({"name": "Doublon", "is_company": True, "ncc": "1234567 a"})
        # Le même NCC reste possible dans une autre société Odoo.
        other_company = self.setup_other_company()["company"]
        self.Partner.create({"name": "Filiale", "ncc": "1234567A", "company_id": other_company.id})

    def _invoice_html(self, partner):
        invoice = self._create_invoice_one_line(price_unit=1000, partner_id=partner.id, post=True)
        html, _type = self.env["ir.actions.report"]._render_qweb_html("account.account_invoices", invoice.ids)
        return html.decode()

    def test_invoice_conditional_display(self):
        # Rien de renseigné : aucune ligne NCC / RCCM.
        html = self._invoice_html(self.customer)
        self.assertNotIn("NCC:", html)
        self.assertNotIn("RCCM:", html)

        # Client avec NCC seulement, facturé via un contact enfant.
        self.customer.ncc = "7654321B"
        contact = self.Partner.create({"name": "Awa Koné", "parent_id": self.customer.id})
        html = self._invoice_html(contact)
        self.assertIn("7654321B", html)
        self.assertNotIn("RCCM:", html)
        self.assertNotIn('name="company_ncc_rccm"', html)

        # Ma société renseignée : son bloc apparaît.
        self.env.company.partner_id.write({"ncc": "1111111C", "rccm": "CI-ABJ-2020-B-1"})
        html = self._invoice_html(self.customer)
        self.assertIn('name="company_ncc_rccm"', html)
        self.assertIn("1111111C", html)
        self.assertIn("CI-ABJ-2020-B-1", html)

    def test_company_fields(self):
        # Saisis depuis la fiche société, stockés et normalisés sur son partenaire.
        company = self.env.company
        company.write({"ncc": " 2222222 d ", "rccm": "ci-abj-2021-b-7"})
        self.assertEqual(company.partner_id.ncc, "2222222D")
        self.assertEqual(company.rccm, "CI-ABJ-2021-B-7")
        with self.assertRaises(ValidationError):
            company.ncc = "ABC"
