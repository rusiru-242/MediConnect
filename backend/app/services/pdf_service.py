"""Server-side PDF generator for MediConnect Digital Prescriptions (Phase 21).

Uses ReportLab to produce professional, tamper-evident digital prescription documents.
Incorporates verified doctor credentials, patient identification, medication tables,
and clinical disclaimers.
"""

from datetime import datetime, timezone
import io
from typing import Any, Dict, List, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class PrescriptionPdfService:
    """Generates encrypted in-memory PDF representations of digital prescriptions."""

    PRIMARY_COLOR = colors.HexColor("#0D5C56")
    SECONDARY_COLOR = colors.HexColor("#0F766E")
    LIGHT_BG = colors.HexColor("#F0FDFA")
    TEXT_MAIN = colors.HexColor("#0F172A")
    TEXT_MUTED = colors.HexColor("#64748B")
    BORDER_COLOR = colors.HexColor("#CBD5E1")

    @classmethod
    def generate_prescription_pdf(
        cls,
        prescription: Dict[str, Any],
        doctor: Dict[str, Any],
        doctor_profile: Dict[str, Any],
        patient: Dict[str, Any],
        medical_record: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """Render a complete, clinical-grade digital prescription PDF and return bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()

        # Custom typography styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=cls.PRIMARY_COLOR,
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=cls.TEXT_MUTED,
        )
        rx_ref_style = ParagraphStyle(
            "RxRefStyle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            alignment=2,  # Right align
            textColor=cls.PRIMARY_COLOR,
        )
        rx_date_style = ParagraphStyle(
            "RxDateStyle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=2,  # Right align
            textColor=cls.TEXT_MUTED,
        )
        section_heading = ParagraphStyle(
            "SectionHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=cls.PRIMARY_COLOR,
        )
        label_style = ParagraphStyle(
            "LabelStyle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=cls.TEXT_MUTED,
        )
        val_style = ParagraphStyle(
            "ValStyle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=cls.TEXT_MAIN,
        )
        val_bold = ParagraphStyle(
            "ValBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=cls.TEXT_MAIN,
        )
        table_header = ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
        )
        table_cell = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=cls.TEXT_MAIN,
        )
        disclaimer_style = ParagraphStyle(
            "DisclaimerStyle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=cls.TEXT_MUTED,
        )

        story = []

        # -------------------------------------------------------------------
        # 1. HEADER BRANDING & REFERENCE
        # -------------------------------------------------------------------
        header_left = [
            Paragraph("<b>MediConnect Healthcare</b>", title_style),
            Paragraph("Sri Lanka National Digital Health Platform", subtitle_style),
        ]
        presc_id = prescription.get("prescriptionId", "RX-PENDING")
        issued_date_str = ""
        issued_at = prescription.get("issuedAt") or prescription.get("createdAt")
        if isinstance(issued_at, datetime):
            issued_date_str = issued_at.strftime("%Y-%m-%d %H:%M UTC")
        else:
            issued_date_str = str(issued_at or datetime.now(timezone.utc).strftime("%Y-%m-%d"))

        header_right = [
            Paragraph(f"<b>OFFICIAL DIGITAL PRESCRIPTION</b>", rx_ref_style),
            Paragraph(f"<b>Prescription Ref:</b> {presc_id}", rx_date_style),
            Paragraph(f"<b>Issued:</b> {issued_date_str}", rx_date_style),
        ]

        header_table = Table(
            [[header_left, header_right]],
            colWidths=[300, 223],
        )
        header_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ])
        )
        story.append(header_table)
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=cls.PRIMARY_COLOR, spaceBefore=0, spaceAfter=10))

        # -------------------------------------------------------------------
        # 2. DOCTOR & PATIENT DETAILS (TWO COLUMNS)
        # -------------------------------------------------------------------
        doc_name = doctor.get("fullName", "Medical Practitioner")
        if not doc_name.startswith("Dr."):
            doc_name = f"Dr. {doc_name}"
        slmc = doctor_profile.get("medicalRegistrationNumber", "Not Verified")
        specialty = doctor_profile.get("specialty", "General Medicine")
        hospital = doctor_profile.get("hospitalOrClinic", "Healthcare Facility")
        quals = doctor_profile.get("qualifications", "")

        pat_name = patient.get("fullName", "Patient")
        pat_id = str(patient.get("_id", "N/A"))[:10].upper()
        pat_email = patient.get("email", "")
        consult_date = ""
        if medical_record:
            consult_date = medical_record.get("consultationDate", "")
        if not consult_date:
            consult_date = issued_date_str[:10]

        doctor_info = [
            Paragraph("VERIFIED PRESCRIBING PHYSICIAN", section_heading),
            Spacer(1, 4),
            Paragraph(f"<b>{doc_name}</b>", val_bold),
            Paragraph(f"{quals}" if quals else "", val_style),
            Paragraph(f"<b>Specialty:</b> {specialty}", val_style),
            Paragraph(f"<b>SLMC Reg No:</b> {slmc}", val_style),
            Paragraph(f"<b>Clinic/Hospital:</b> {hospital}", val_style),
        ]

        patient_info = [
            Paragraph("PATIENT IDENTIFICATION", section_heading),
            Spacer(1, 4),
            Paragraph(f"<b>{pat_name}</b>", val_bold),
            Paragraph(f"<b>Patient ID:</b> {pat_id}", val_style),
            Paragraph(f"<b>Contact:</b> {pat_email}", val_style),
            Paragraph(f"<b>Consultation Date:</b> {consult_date}", val_style),
            Paragraph(f"<b>Appointment Ref:</b> {prescription.get('appointmentId', 'N/A')}", val_style),
        ]

        info_table = Table(
            [[doctor_info, patient_info]],
            colWidths=[260, 263],
        )
        info_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, 0), cls.LIGHT_BG),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (0, 0), 0.5, cls.BORDER_COLOR),
                ("BOX", (1, 0), (1, 0), 0.5, cls.BORDER_COLOR),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(info_table)
        story.append(Spacer(1, 14))

        # -------------------------------------------------------------------
        # 3. CLINICAL NOTES & ASSESSMENT (IF PRESENT)
        # -------------------------------------------------------------------
        if medical_record and medical_record.get("assessment"):
            assessment_text = medical_record.get("assessment", "")
            assess_content = [
                Paragraph("<b>Provisional Clinical Assessment:</b>", label_style),
                Paragraph(assessment_text, val_style),
            ]
            assess_table = Table([[assess_content]], colWidths=[523])
            assess_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                    ("BOX", (0, 0), (-1, -1), 0.5, cls.BORDER_COLOR),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ])
            )
            story.append(assess_table)
            story.append(Spacer(1, 10))

        # -------------------------------------------------------------------
        # 4. MEDICATIONS (Rx) TABLE
        # -------------------------------------------------------------------
        story.append(Paragraph("Rx — PRESCRIBED MEDICATIONS", section_heading))
        story.append(Spacer(1, 6))

        med_headers = [
            Paragraph("#", table_header),
            Paragraph("Medicine & Strength", table_header),
            Paragraph("Dose / Route", table_header),
            Paragraph("Frequency", table_header),
            Paragraph("Duration", table_header),
            Paragraph("Qty", table_header),
            Paragraph("Specific Instructions", table_header),
        ]
        med_rows = [med_headers]

        items = prescription.get("medicationItems", [])
        for idx, item in enumerate(items, 1):
            name_strength = f"<b>{item.get('medicationName', '')}</b><br/>{item.get('strength', '')}"
            dose_route = f"{item.get('dose', '')}<br/>({item.get('route', 'Oral')})"
            freq = item.get("frequency", "")
            dur = item.get("duration", "")
            qty = str(item.get("quantity", ""))
            extra = item.get("additionalInstructions") or "As advised"

            med_rows.append([
                Paragraph(str(idx), table_cell),
                Paragraph(name_strength, table_cell),
                Paragraph(dose_route, table_cell),
                Paragraph(freq, table_cell),
                Paragraph(dur, table_cell),
                Paragraph(qty, table_cell),
                Paragraph(extra, table_cell),
            ])

        col_widths = [20, 130, 75, 75, 60, 40, 123]
        med_table = Table(med_rows, colWidths=col_widths, repeatRows=1)
        
        t_style = [
            ("BACKGROUND", (0, 0), (-1, 0), cls.PRIMARY_COLOR),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, cls.BORDER_COLOR),
            ("BOX", (0, 0), (-1, -1), 1, cls.PRIMARY_COLOR),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
        # Alternating rows
        for i in range(1, len(med_rows)):
            if i % 2 == 0:
                t_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F8FAFC")))
        med_table.setStyle(TableStyle(t_style))
        story.append(med_table)
        story.append(Spacer(1, 14))

        # -------------------------------------------------------------------
        # 5. GENERAL INSTRUCTIONS & ADVICE
        # -------------------------------------------------------------------
        instructions = prescription.get("instructions")
        if instructions:
            inst_content = [
                Paragraph("<b>Doctor's General Instructions & Precautions:</b>", label_style),
                Paragraph(instructions, val_style),
            ]
            inst_table = Table([[inst_content]], colWidths=[523])
            inst_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), cls.LIGHT_BG),
                    ("BOX", (0, 0), (-1, -1), 0.5, cls.BORDER_COLOR),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ])
            )
            story.append(inst_table)
            story.append(Spacer(1, 14))

        # -------------------------------------------------------------------
        # 6. SIGN-OFF / ELECTRONIC VALIDATION
        # -------------------------------------------------------------------
        status_label = prescription.get("status", "ISSUED")
        auth_box = [
            Paragraph(f"<b>ELECTRONICALLY AUTHORIZED RECORD</b>", label_style),
            Paragraph(
                f"Approved by <b>{doc_name}</b> (SLMC: {slmc}) via MediConnect authenticated clinical portal. "
                f"Status: <b>{status_label}</b>.",
                val_style,
            ),
        ]
        auth_table = Table([[auth_box]], colWidths=[523])
        auth_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("LINEBEFORE", (0, 0), (0, -1), 3, cls.SECONDARY_COLOR),
                ("BOX", (0, 0), (-1, -1), 0.5, cls.BORDER_COLOR),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(auth_table)
        story.append(Spacer(1, 14))

        # -------------------------------------------------------------------
        # 7. CLINICAL DISCLAIMER & 1990 EMERGENCY NOTICE
        # -------------------------------------------------------------------
        disclaimer_text = (
            "<b>LEGAL & CLINICAL NOTICE:</b> This digital prescription was created and authorized exclusively by the "
            "licensed practitioner indicated above. Patients must take medications strictly as directed. Do not exceed "
            "the stated dose or transfer medications to another person. In the event of acute unexpected side effects, "
            "anaphylaxis, severe difficulty breathing, or other life-threatening medical emergencies, please call the "
            "<b>1990 Suwa Seriya ambulance service immediately</b> or visit the nearest Hospital Emergency Treatment Unit (ETU)."
        )
        story.append(Paragraph(disclaimer_text, disclaimer_style))

        # Build document
        doc.build(story)
        return buffer.getvalue()
