"""Generate a sample resume PDF for testing the pipeline with Sushant Kumar's details.

Uses reportlab to create a realistic PDF resume.
Run: python generate_resume.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
)
from pathlib import Path


def generate_resume():
    output_path = Path(__file__).parent / "input" / "resume.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    name_style = ParagraphStyle(
        "Name",
        parent=styles["Title"],
        fontSize=20,
        spaceAfter=4,
        alignment=TA_CENTER,
    )

    contact_style = ParagraphStyle(
        "Contact",
        parent=styles["Normal"],
        fontSize=9,
        alignment=TA_CENTER,
        spaceAfter=8,
    )

    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=4,
        textColor=HexColor("#2c3e50"),
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=4,
        leading=14,
    )

    bold_body_style = ParagraphStyle(
        "BoldBody",
        parent=body_style,
        fontName="Helvetica-Bold",
    )

    # Build content
    story = []

    # Name
    story.append(Paragraph("Sushant Kumar", name_style))

    # Contact
    story.append(Paragraph(
        "sushant14300@gmail.com | +91-6207851006 | Phagwara, Punjab",
        contact_style,
    ))
    story.append(Paragraph(
        "LinkedIn: https://linkedin.com/in/sushant-kumar-97978b28b | GitHub: https://github.com/sushantkumar143",
        contact_style,
    ))

    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#2c3e50")))

    # Experience / Internships
    story.append(Paragraph("Internship & Training", section_style))

    story.append(Paragraph("AICTE - Edunet Foundation | IBM SkillsBuild | Virtual Internship", bold_body_style))
    story.append(Paragraph("Sep 2025 - Oct 2025", body_style))
    story.append(Paragraph(
        "• Built and deployed 3+ machine learning applications integrating AI and cloud-based workflows.<br/>"
        "• Processed and visualized datasets containing 10,000+ records using Pandas, NumPy, and Matplotlib.<br/>"
        "• Collaborated in a virtual team environment to deliver AI-driven prototypes within strict project deadlines.",
        body_style,
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Competitive Programming | Lovely Professional University | Summer Training", bold_body_style))
    story.append(Paragraph("Jun 2025 - Jul 2025", body_style))
    story.append(Paragraph(
        "• Solved 500+ algorithmic problems across LeetCode and Codeforces covering graphs, Dynamic Programming, greedy, and advanced data structures.<br/>"
        "• Improved competitive programming ranking by 65% through consistent optimization of time and space complexity.<br/>"
        "• Reduced average solution runtime by 30-40% using STL optimization and advanced algorithmic techniques.",
        body_style,
    ))

    # Projects
    story.append(Paragraph("Projects", section_style))

    story.append(Paragraph("RAONE - Enterprise AI Copilot with Hybrid RAG & LLM Orchestration", bold_body_style))
    story.append(Paragraph("Mar 2026 - Apr 2026", body_style))
    story.append(Paragraph(
        "• Engineered a multi-tenant SaaS AI copilot supporting secure chatbot interactions over private knowledge bases using Hybrid RAG architecture.<br/>"
        "• Integrated Dense + Sparse retrieval pipelines with FAISS and BM25, improving contextual response relevance and retrieval efficiency.<br/>"
        "• Implemented LLM orchestration with Groq, OpenRouter, HuggingFace, and Ollama fallback systems ensuring high availability.<br/>"
        "• Developed scalable FastAPI backend APIs and React dashboard supporting API-key based third-party chatbot integrations.",
        body_style,
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("VisionTraffic - Smart Vehicle Traffic Monitoring System", bold_body_style))
    story.append(Paragraph("Apr 2025 - May 2025", body_style))
    story.append(Paragraph(
        "• Developed a real-time AI-powered traffic monitoring system capable of vehicle detection, classification, speed estimation, anomaly detection, and OCR-based license plate recognition.<br/>"
        "• Trained and optimized YOLOv8 models on 900+ annotated traffic instances across 7 vehicle classes.",
        body_style,
    ))

    # Education
    story.append(Paragraph("Education", section_style))
    story.append(Paragraph("Lovely Professional University | Bachelor of Technology - Computer Science and Engineering", bold_body_style))
    story.append(Paragraph("Since August 2023 | CGPA: 9.12", body_style))

    # Skills
    story.append(Paragraph("Skills", section_style))
    story.append(Paragraph(
        "C++, Python, C, Java, JavaScript, React, HTML, CSS, FastAPI, Linux, Docker, AWS, Jenkins, Hadoop, "
        "Matplotlib, NumPy, Pandas, Seaborn, Scikit-learn, LLMs, RAG, FAISS, BM25",
        body_style,
    ))

    doc.build(story)
    print(f"Resume generated: {output_path}")


if __name__ == "__main__":
    generate_resume()
