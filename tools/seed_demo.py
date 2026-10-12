# Demo data for the store screenshots (invented names, no personal data). Run in `odoo-bin shell`:
#   odoo-bin shell -c <conf> -d <db> --no-http < tools/seed_demo.py
# Prints DEMO_WIZARD=<id> lines for tools/screenshots.mjs. Idempotent enough for a throw-away databank.
import random
from datetime import date, timedelta

random.seed(7)
company = env.company
company.write({'name': 'Fjord Consulting', 'street': 'Havenlaan 12', 'city': 'Gent', 'zip': '9000',
               'country_id': env.ref('base.be').id, 'email': 'info@fjord.example', 'phone': '+32 9 000 00 00'})
env['res.users'].browse(2).write({'password': 'admin'})
Partner, Project, Task, Employee = env['res.partner'], env['project.project'], env['project.task'], env['hr.employee']
harbor = Partner.create({'name': 'Harbor Logistics', 'is_company': True})
north = Partner.create({'name': 'Northwind Foods', 'is_company': True})
people = [Employee.create({'name': n, 'job_title': j}) for n, j in
          (('Astrid Berg', 'Consultant'), ('Leif Hansen', 'Developer'), ('Sigrid Dahl', 'Project manager'))]
projects = {
    'Website relaunch': (harbor, ['Design', 'Development', 'Content']),
    'ERP rollout': (north, ['Analysis', 'Data migration', 'Training']),
}
tasks = []
for pname, (partner, tnames) in projects.items():
    project = Project.create({'name': pname, 'partner_id': partner.id, 'allow_timesheets': True})
    tasks += [Task.create({'name': t, 'project_id': project.id}) for t in tnames]
words = ['Workshop', 'Wireframes', 'Review', 'Call with customer', 'Implementation', 'Testing', 'Mapping',
         'Import run', 'User training', 'Documentation']
Line = env['account.analytic.line']
day = date(2026, 9, 1)
while day <= date(2026, 9, 30):
    if day.weekday() < 5:
        for emp in people:
            for _i in range(random.randint(1, 3)):
                task = random.choice(tasks)
                Line.create({'employee_id': emp.id, 'project_id': task.project_id.id, 'task_id': task.id, 'date': day,
                             'unit_amount': random.choice([0.5, 0.75, 1, 1.5, 2, 2.5, 3, 4]), 'name': random.choice(words)})
    day += timedelta(days=1)
if 'ss.timesheet.pdf.wizard' in env:
    W = env['ss.timesheet.pdf.wizard']
    w1 = W.create({'period': 'custom', 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30),
                   'employee_ids': [(6, 0, [people[0].id])], 'section_by': 'employee', 'group_by': 'date'})
    w2 = W.create({'period': 'custom', 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30),
                   'project_ids': [(6, 0, Project.search([('name', '=', 'Website relaunch')]).ids)],
                   'section_by': 'project', 'group_by': 'task', 'show_details': False, 'show_signatures': True,
                   'signature_left': 'Fjord Consulting', 'signature_right': 'Customer approval'})
    print('DEMO_WIZARD_EMPLOYEE=%d' % w1.id)
    print('DEMO_WIZARD_PROJECT=%d' % w2.id)
if 'tv.timesheet.report.wizard' in env:
    w = env['tv.timesheet.report.wizard'].with_user(env.ref('base.user_admin')).create({'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30),
                                                   'employee_ids': [(6, 0, [p.id for p in people[:2]])]})
    print('DEMO_TV_WIZARD=%d' % w.id)
if 'ss_timesheet_report_on_invoice' in env['res.company']._fields and env['account.journal'].search([('type', '=', 'sale')], limit=1):
    company.ss_timesheet_report_on_invoice = True
    product = env['product.product'].create({'name': 'Consulting (hours)', 'type': 'service', 'list_price': 95.0})
    lines = Line.search([('project_id.partner_id', '=', north.id)])
    move = env['account.move'].create({'move_type': 'out_invoice', 'partner_id': north.id, 'invoice_date': date(2026, 9, 30),
                                       'invoice_line_ids': [(0, 0, {'product_id': product.id, 'quantity': sum(lines.mapped('unit_amount')),
                                                                    'price_unit': 95.0})]})
    lines.write({'timesheet_invoice_id': move.id})
    move.action_post()
    print('DEMO_INVOICE=%d' % move.id)
env.cr.commit()
