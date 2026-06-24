from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    PageBreak,
    KeepTogether,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "generated_docs"
OUT_DIR.mkdir(exist_ok=True)
PDF_PATH = OUT_DIR / "it_support_portal_management_documentation.pdf"
ASSET_DIR = OUT_DIR / "assets"
ASSET_DIR.mkdir(exist_ok=True)


def load_font(size: int, bold: bool = False):
    candidates = [
        ("C:/Windows/Fonts/segoeui.ttf", False),
        ("C:/Windows/Fonts/segoeuib.ttf", True),
        ("C:/Windows/Fonts/arial.ttf", False),
        ("C:/Windows/Fonts/arialbd.ttf", True),
    ]
    for path, is_bold in candidates:
        if bold == is_bold and Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def make_mock_screenshot(title, subtitle, stats, sections, path, accent="#4F46E5"):
    img = Image.new("RGB", (1600, 900), "#0B1220")
    draw = ImageDraw.Draw(img)
    header_h = 96
    draw.rounded_rectangle((32, 32, 1568, 868), radius=28, fill="#F8FAFC")
    draw.rounded_rectangle((32, 32, 1568, 128), radius=28, fill="#0F172A")
    draw.rectangle((32, 96, 1568, 128), fill="#0F172A")
    draw.ellipse((70, 58, 102, 90), fill=accent)
    draw.text((120, 58), "IT Support Portal", font=load_font(28, True), fill="white")
    draw.text((120, 96), title, font=load_font(20, False), fill="#CBD5E1")
    draw.text((72, 170), title, font=load_font(44, True), fill="#0F172A")
    draw.text((72, 222), subtitle, font=load_font(22), fill="#475569")

    x = 72
    y = 290
    for label, value, color in stats:
        draw.rounded_rectangle((x, y, x + 300, y + 150), radius=22, fill="white", outline="#E2E8F0", width=2)
        draw.rounded_rectangle((x + 18, y + 18, x + 74, y + 74), radius=16, fill=color)
        draw.text((x + 96, y + 28), label, font=load_font(18), fill="#64748B")
        draw.text((x + 96, y + 62), value, font=load_font(34, True), fill="#0F172A")
        x += 330

    panel_y = 480
    for i, section in enumerate(sections):
        sx = 72 + i * 480
        draw.rounded_rectangle((sx, panel_y, sx + 420, panel_y + 290), radius=22, fill="white", outline="#E2E8F0", width=2)
        draw.text((sx + 24, panel_y + 20), section["heading"], font=load_font(22, True), fill="#0F172A")
        draw.text((sx + 24, panel_y + 58), section["subheading"], font=load_font(15), fill="#64748B")
        ry = panel_y + 100
        for row in section["rows"]:
            draw.rounded_rectangle((sx + 24, ry, sx + 396, ry + 44), radius=12, fill="#F8FAFC")
            draw.text((sx + 36, ry + 11), row, font=load_font(16), fill="#334155")
            ry += 54

    img.save(path)


def make_cover(path):
    img = Image.new("RGB", (1600, 900), "#09111F")
    draw = ImageDraw.Draw(img)
    for i, color in enumerate(["#4F46E5", "#7C3AED", "#0EA5E9", "#10B981"]):
        draw.ellipse((1100 + i * 60, 80 + i * 40, 1450, 430 + i * 40), outline=color, width=8)
    draw.rounded_rectangle((78, 78, 920, 820), radius=36, fill="#0F172A", outline="#243042", width=2)
    draw.text((130, 150), "IT Support Portal", font=load_font(56, True), fill="white")
    draw.text((130, 232), "Management Documentation", font=load_font(34), fill="#CBD5E1")
    body = (
        "A complete overview of the portal's workflows, modules, controls, and business impact."
    )
    draw.text((130, 330), "\n".join(wrap(body, width=45)), font=load_font(23), fill="#94A3B8")
    items = [
        "Role-based access for Super Admin, HR, IT Specialist, and Employee",
        "Asset, license, and allocation governance",
        "Onboarding, SOP, ticketing, and integration workflows",
        "Operational dashboards for leadership visibility",
    ]
    y = 490
    for item in items:
        draw.rounded_rectangle((130, y, 860, y + 74), radius=18, fill="#111C33")
        draw.ellipse((154, y + 20, 182, y + 48), fill="#4F46E5")
        draw.text((202, y + 20), item, font=load_font(20), fill="#E2E8F0")
        y += 92
    draw.text((130, 728), "Generated for management review", font=load_font(18), fill="#64748B")
    img.save(path)


def build_pdf():
    cover = ASSET_DIR / "cover.png"
    dash = ASSET_DIR / "dashboard.png"
    tickets = ASSET_DIR / "tickets.png"
    inventory = ASSET_DIR / "inventory.png"
    operations = ASSET_DIR / "operations.png"
    orgs = ASSET_DIR / "orgs.png"

    make_cover(cover)
    make_mock_screenshot(
        "Executive Dashboard",
        "Role-aware KPIs, asset health, onboarding pipeline, and leadership shortcuts.",
        [
            ("Employees", "1,248", "#4F46E5"),
            ("Open Tickets", "37", "#EF4444"),
            ("Available Assets", "214", "#10B981"),
        ],
        [
            {
                "heading": "At-a-glance value",
                "subheading": "Leadership can see what needs attention immediately.",
                "rows": [
                    "Open incidents and outstanding support work",
                    "Asset mix by type and category",
                    "MDM coverage by platform",
                ],
            },
            {
                "heading": "Quick actions",
                "subheading": "One-click access to admin workflows.",
                "rows": [
                    "Organisations management",
                    "Inventory and allocation operations",
                    "SOP execution and monitoring",
                ],
            },
        ],
        dash,
        "#4F46E5",
    )
    make_mock_screenshot(
        "Support Tickets",
        "Raise, assign, discuss, resolve, and close service requests with full traceability.",
        [
            ("Priority", "Critical", "#EF4444"),
            ("Status", "Open", "#F59E0B"),
            ("Comments", "12", "#0EA5E9"),
        ],
        [
            {
                "heading": "Workflow",
                "subheading": "End-to-end request handling.",
                "rows": [
                    "Ticket creation by any authenticated user",
                    "Assignment to support staff",
                    "Resolve and close controls for IT roles",
                ],
            },
            {
                "heading": "Conversation trail",
                "subheading": "Every ticket keeps a visible discussion history.",
                "rows": [
                    "Timestamped comments",
                    "Status transitions",
                    "Ownership changes",
                ],
            },
        ],
        tickets,
        "#EF4444",
    )
    make_mock_screenshot(
        "Inventory & Allocation",
        "Hardware and software inventory, dynamic attributes, bulk upload, and QR-linked allocations.",
        [
            ("Asset Types", "18", "#4F46E5"),
            ("Licenses", "74", "#0EA5E9"),
            ("Recovered", "31", "#10B981"),
        ],
        [
            {
                "heading": "Controls",
                "subheading": "Inventory is configurable instead of hard coded.",
                "rows": [
                    "Asset types and attribute definitions",
                    "Bulk Excel upload and templates",
                    "Hardware and software allocation queues",
                ],
            },
            {
                "heading": "Operational traceability",
                "subheading": "Each assignment can be traced to a person and status.",
                "rows": [
                    "QR label generation",
                    "Recovery and revocation flows",
                    "Asset device dashboard and installed apps",
                ],
            },
        ],
        inventory,
        "#0EA5E9",
    )
    make_mock_screenshot(
        "HR and Org Structure",
        "Employee profiles, onboarding requests, client memberships, and locations.",
        [
            ("Onboarding", "14", "#F59E0B"),
            ("Client Orgs", "8", "#7C3AED"),
            ("Locations", "23", "#10B981"),
        ],
        [
            {
                "heading": "People lifecycle",
                "subheading": "From new joiner request to active employee.",
                "rows": [
                    "Employee directory and detail dashboards",
                    "New joiner intake and confirmation",
                    "Client organisation member profiles",
                ],
            },
            {
                "heading": "Governance",
                "subheading": "Organisations remain structured and auditable.",
                "rows": [
                    "Base organisation protection",
                    "Location management",
                    "Role-restricted admin access",
                ],
            },
        ],
        orgs,
        "#7C3AED",
    )
    make_mock_screenshot(
        "Operations Library",
        "SOP creation, categorisation, and step-by-step execution for repeatable support delivery.",
        [
            ("SOPs", "41", "#4F46E5"),
            ("Steps", "287", "#10B981"),
            ("Automation", "12", "#0EA5E9"),
        ],
        [
            {
                "heading": "Standardisation",
                "subheading": "Teams follow consistent procedures.",
                "rows": [
                    "Manual, automated, approval, and checklist steps",
                    "Searchable SOP repository by category",
                    "Execution wizard with progress tracking",
                ],
            },
            {
                "heading": "Integration",
                "subheading": "SOPs support repeatable operational outcomes.",
                "rows": [
                    "Onboarding playbooks",
                    "Device setup and recoveries",
                    "Service desk operating procedures",
                ],
            },
        ],
        operations,
        "#10B981",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TitleLarge",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#111827"),
        spaceAfter=8,
        spaceBefore=10,
    ))
    styles.add(ParagraphStyle(
        name="Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#334155"),
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="Small",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#64748B"),
    ))

    doc = BaseDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")

    def on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#0F172A"))
        canvas.rect(0, A4[1] - 22 * mm, A4[0], 22 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(14 * mm, A4[1] - 12.5 * mm, "IT Support Portal")
        canvas.setFont("Helvetica", 8.5)
        canvas.drawRightString(A4[0] - 14 * mm, A4[1] - 12.5 * mm, "Management Documentation")
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.line(14 * mm, 11 * mm, A4[0] - 14 * mm, 11 * mm)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(A4[0] - 14 * mm, 7.5 * mm, f"Page {_doc.page}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=on_page)])

    story = []
    story.append(Spacer(1, 10 * mm))
    story.append(RLImage(str(cover), width=180 * mm, height=101 * mm))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Executive Summary", styles["TitleLarge"]))
    story.append(Paragraph(
        "The IT Support Portal is a role-aware operational platform that unifies support tickets, employee records, onboarding, "
        "inventory governance, asset allocation, SOP execution, organisation management, and MDM integration. It reduces manual "
        "coordination, improves visibility for management, and creates a reliable system of record for day-to-day IT operations.",
        styles["Body"],
    ))
    story.append(Spacer(1, 4 * mm))

    summary_data = [
        ["Business Area", "What the portal does", "Management value"],
        ["Support", "Centralises ticket intake, assignment, comments, and closure", "Faster resolution and transparent service history"],
        ["People", "Maintains employees, onboarding, client profiles, and org structures", "Cleaner workforce records and smoother joiner flow"],
        ["Assets", "Manages hardware, software, allocation, recovery, and QR labels", "Lower asset loss and better spend control"],
        ["Standards", "Creates and executes SOPs with checklist steps", "More consistent operations across teams"],
        ["Integrations", "Connects to SureMDM and imported installed-app data", "Better endpoint visibility and automated sync"],
    ]
    table = Table(summary_data, colWidths=[28 * mm, 85 * mm, 58 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#334155")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D6DCE5")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 6 * mm))

    sections = [
        ("1. Core Features", [
            "Dashboard with live KPIs, charts, and role-based shortcuts.",
            "Support ticketing with create, view, assign, resolve, close, and comment workflows.",
            "Employee directory with filtering by organisation and core process.",
            "Employee detail dashboard with identity, organisation, email, and assigned asset history.",
            "New joiner onboarding with request intake, confirmation, and rejection controls.",
            "Inventory management for hardware and software with configurable attributes.",
            "Bulk asset template download and Excel upload for faster data onboarding.",
            "Asset allocation for both hardware and software, including recovery and revocation.",
            "QR code generation and printable labels for assigned hardware.",
            "Device dashboard showing MDM data, installed applications, and imported report upload.",
            "Inventory configuration for asset types and custom attributes.",
            "SOP repository with search, categories, step-by-step detail, and execution mode.",
            "User management with roles and activation state control.",
            "Organisation directory with base and client orgs, locations, and member profiles.",
            "SureMDM integration setup, testing, syncing, and device filtering.",
        ]),
        ("2. Role-Based Access", [
            "Super Admin can access all modules, including user and organisation administration.",
            "HR can manage employees and onboarding workflows.",
            "IT Specialist can manage inventory, allocation, SOPs, integrations, and support operations.",
            "Employees can use the portal for tickets and self-service where permitted.",
        ]),
        ("3. Why It Matters", [
            "Reduces time spent on spreadsheets, email chains, and manual handoffs.",
            "Improves accountability with status histories, comments, and audit-friendly records.",
            "Gives leadership real-time visibility into support demand and asset availability.",
            "Supports faster onboarding and asset provisioning for new joiners.",
            "Lowers risk through structured access control and standard operating procedures.",
        ]),
    ]

    for title, bullets in sections:
        story.append(Paragraph(title, styles["Section"]))
        for bullet in bullets:
            story.append(Paragraph(f"• {bullet}", styles["Body"]))
        story.append(Spacer(1, 2 * mm))

    story.append(PageBreak())
    story.append(Paragraph("Feature Walkthrough With Visual References", styles["TitleLarge"]))
    story.append(Paragraph(
        "The following panels mirror the main portal areas and help management understand how each module supports daily operations.",
        styles["Body"],
    ))
    story.append(Spacer(1, 4 * mm))

    screenshot_blocks = [
        ("Executive dashboard", "The landing page gives management immediate operational visibility across employees, tickets, assets, MDM systems, and pending onboarding."),
        ("Support tickets", "Users can raise incidents, support staff can assign work, change status, and keep the discussion in one place."),
        ("Inventory and allocation", "The inventory module manages configurable asset types, bulk uploads, hardware recovery, and software licences."),
        ("Organisation management", "Org structures, member profiles, and locations are maintained centrally for clean governance."),
        ("SOP management", "Procedures are searchable, categorised, and executable step by step for repeatable service delivery."),
    ]

    image_paths = [dash, tickets, inventory, orgs, operations]
    for i, (heading, text) in enumerate(screenshot_blocks):
        story.append(KeepTogether([
            Paragraph(heading, styles["Section"]),
            RLImage(str(image_paths[i]), width=180 * mm, height=101 * mm),
            Spacer(1, 2 * mm),
            Paragraph(text, styles["Body"]),
            Spacer(1, 4 * mm),
        ]))

    story.append(PageBreak())
    story.append(Paragraph("Recommended Management Benefits", styles["TitleLarge"]))
    benefit_data = [
        ["Benefit", "Explanation"],
        ["Operational visibility", "Leadership can see support demand, asset health, onboarding load, and MDM coverage in one system."],
        ["Lower manual effort", "Bulk uploads, configurable attributes, and reusable SOPs cut down repetitive administration."],
        ["Improved control", "Role-based access keeps HR, IT, admin, and employee actions appropriately separated."],
        ["Traceability", "Tickets, allocations, confirmations, comments, and recoveries all leave a visible history."],
        ["Faster onboarding", "New joiners can be captured, confirmed, provisioned, and tracked with fewer handoffs."],
        ["Better asset stewardship", "Hardware and software inventory are managed with assignment, recovery, and utilisation views."],
    ]
    bt = Table(benefit_data, colWidths=[40 * mm, 131 * mm], repeatRows=1)
    bt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(bt)
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        "Overall, the portal acts as a single operating layer for IT and HR workstreams. It is especially useful when management needs a dependable "
        "view of service volume, hardware allocation, onboarding readiness, and compliance with internal procedures.",
        styles["Body"],
    ))

    doc.build(story)


if __name__ == "__main__":
    build_pdf()
    print(PDF_PATH)
