from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageTemplate, Frame, BaseDocTemplate
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import re
import json
import base64
from io import BytesIO
from bs4 import BeautifulSoup
import os

from PIL import Image as PILImage
from getdataAPI import getData
import uuid


def process_json_string(json_str):
    """Process and clean JSON string before parsing."""
    # Replace problematic escape sequences
    cleaned_str = json_str.replace('\\"', '"')
    cleaned_str = cleaned_str.replace('\\(', '(')
    cleaned_str = cleaned_str.replace('\\)', ')')
    # Handle any other problematic characters as needed
    return cleaned_str


def normalize_json_values(obj):
    """
    Recursively normalize JSON values:
    - 'False' -> False
    - 'true' -> True
    - 'null' -> None
    - Handles both string and actual boolean/null values
    """
    if isinstance(obj, dict):
        return {
            key: normalize_json_values(value)
            for key, value in obj.items()
        }
    elif isinstance(obj, list):
        return [normalize_json_values(item) for item in obj]
    elif isinstance(obj, str):
        if obj.lower() == 'false':
            return False
        elif obj.lower() == 'true':
            return True
        elif obj.lower() == 'null':
            return None
        return obj
    return obj


def extract_base64_image(html_content):
    """Extract base64 image data from HTML content."""
    start_index = html_content.find('data:image/')
    if start_index == -1:
        return None

    base64_start = html_content.find('base64,', start_index) + 7
    base64_end = html_content.find('"', base64_start)
    base64_data = html_content[base64_start:base64_end]

    pattern = r'width="(\d+)" height="(\d+)"'

    # Find all matches in the HTML content
    matches = re.findall(pattern, html_content)

    # Extract the width and height from the first match (if any)
    width, height = matches[0]

    return [base64_data, "png", int(width), int(height)]


def normalize_dimensions(width, height):
    """
    Normalize image dimensions while maintaining aspect ratio.

    Args:
        width (float): Original width
        height (float): Original height

    Returns:
        tuple: (normalized_width, normalized_height)
    """
    # Calculate aspect ratio
    aspect_ratio = height / width if width != 0 else 1

    # Base width normalization
    if width < 32:
        scaled_width = width  # Keep original size for very small images
    elif width >= 200:
        scaled_width = width * 0.1  # Significant reduction for very large images
    else:
        # Smooth scaling based on width ranges
        if width < 50:
            scaled_width = width * 0.6
        elif width < 100:
            scaled_width = width * 0.4
        elif width < 140:
            scaled_width = width * 0.3
        else:
            scaled_width = width * 0.2

    # Calculate height while maintaining aspect ratio
    scaled_height = scaled_width * aspect_ratio

    return scaled_width, scaled_height


def create_image_from_base64(base64_data,
                             width,
                             height,
                             target_width=0.5,
                             target_height=0.5):
    """Create an Image object from base64 data with scaling."""
    if not base64_data:
        return None

    try:
        image_data = base64.b64decode(base64_data)
        image_stream = BytesIO(image_data)
        original_width_points = width
        original_height_points = height
        original_width_points, original_height_points = normalize_dimensions(
            width, height)

        img = Image(image_stream,
                    width=original_width_points,
                    height=original_height_points)
        return img

    except Exception as e:
        print(f"Error creating image: {e}")
        return None

def extract_content_from_html(html_content):
    """Extract both text and images from HTML content."""
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    content_elements = []

    for element in soup.find_all(['p', 'img', 'span']):
        if element.name == 'img':
            # Handle direct images
            base64_data = extract_base64_image(str(element))
            if base64_data:
                content_elements.append(('image', base64_data))
        elif element.name == 'span' and element.get('class') == ['mjpage']:
            # Handle images within spans (like math equations)
            img = element.find('img')
            if img:
                base64_data = extract_base64_image(str(img))
                if base64_data:
                    content_elements.append(('image', base64_data))
        else:
            # Handle text content
            text = element.get_text().strip()
            if text:
                content_elements.append(('text', text))

    return content_elements


class MCQDocTemplate(BaseDocTemplate):

    def __init__(self, filename, **kw):
        super().__init__(filename, **kw)
        template = PageTemplate('normal', [
            Frame(self.leftMargin,
                  self.bottomMargin,
                  self.width,
                  self.height - 0.75 * inch,
                  id='normal')
        ])
        self.addPageTemplates(template)

    def afterPage(self):
        canvas = self.canv
        canvas.saveState()
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.setFont("Times-Roman", 9)
        canvas.drawCentredString(self.pagesize[0] / 2, 30, text)
        canvas.restoreState()


def clean_html(raw_html):
    """Clean HTML content and remove special characters."""
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    cleantext = cleantext.replace('&ndash;', '-')
    cleantext = cleantext.replace('\\(', '')
    cleantext = cleantext.replace('\\)', '')
    return cleantext.strip()


def generate_mcq_pdf(questions, output_filename="mcq_exam.pdf"):
    """Generate PDF with MCQ questions."""
    doc = MCQDocTemplate(output_filename,
                         pagesize=A4,
                         rightMargin=36,
                         leftMargin=36,
                         topMargin=36,
                         bottomMargin=36)

    styles = getSampleStyleSheet()

    # Define styles
    styles.add(
        ParagraphStyle(name='InstituteHeader',
                       fontSize=16,
                       alignment=TA_LEFT,
                       spaceAfter=6,
                       fontName='Times-Bold'))

    styles.add(
        ParagraphStyle(name='ExamHeader',
                       fontSize=12,
                       alignment=TA_LEFT,
                       spaceAfter=20,
                       fontName='Times-Roman'))

    styles.add(
        ParagraphStyle(name='SectionTitle',
                       fontSize=12,
                       alignment=TA_CENTER,
                       spaceAfter=12,
                       fontName='Times-Bold'))

    styles.add(
        ParagraphStyle(name='Instructions',
                       fontSize=10,
                       alignment=TA_CENTER,
                       spaceAfter=20,
                       fontName='Times-Roman'))

    styles.add(
        ParagraphStyle(name='Question',
                       fontSize=11,
                       alignment=TA_LEFT,
                       spaceAfter=6,
                       fontName='Times-Roman',
                       leftIndent=0))

    styles.add(
        ParagraphStyle(name='Options',
                       fontSize=11,
                       alignment=TA_LEFT,
                       spaceAfter=12,
                       fontName='Times-Roman',
                       leftIndent=20))

    # Build content
    story = []

    # Headers
    story.append(Paragraph("Institute of Eximination", styles['InstituteHeader']))
    story.append(
        Paragraph("MODEL ENTRANCE EXAM", styles['ExamHeader']))
    story.append(Paragraph("Believe in yourself. Do great!", styles['SectionTitle']))

    # Add questions
    for i, q in enumerate(questions, 1):
        question_data = q['questionData']

        # Question text
        question_text = clean_html(question_data['question_plain_title'])
        question = Paragraph(f"{i}) {question_text}", styles['Question'])
        story.append(question)

        # Process options
        options = []
        option_keys = [
            'ans1_plain_text', 'ans2_plain_text', 'ans3_plain_text',
            'ans4_plain_text'
        ]

        for j, key in enumerate(option_keys):
            option_content = question_data[key]
            if option_content.startswith('<html>'):
                # Check for base64 image
                base64_data, img_format, width, height = extract_base64_image(
                    option_content)
                if base64_data:
                    img = create_image_from_base64(base64_data,
                                                   width,
                                                   height,
                                                   target_width=0.5,
                                                   target_height=0.5)
                    # img = create_image_from_base64(base64_data)
                    if img:
                        options.append(
                            Paragraph(f"{chr(97 + j)})", styles['Options']))
                        options.append(img)
            else:
                option_text = clean_html(option_content)
                options.append(
                    Paragraph(f"{chr(97 + j)}) {option_text}",
                              styles['Options'])
                )  # Add formatted option as a Paragraph

        # Create options table
        if options:
            # Create a single row with all options
            options_row = []
            for option in options:
                options_row.append(
                    option
                )  # Directly add each option (either Paragraph or image)

            # Create a table with a single row
            table = Table([options_row])  # Each inner list is a row
            table.setStyle(
                TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ]))
            story.append(table)

        # # Add page break after every 10 questionsif i % 10 == 0 and i != len(questions):
        #     story.append(PageBreak())

    # Generate PDF
    doc.build(story)


def main(output_filename="session_2.pdf"):
    """Main function to process JSON and generate PDF."""
    try:
        # Clean and parse JSON
        json_data=getData()
        # Normalize the data
        normalized_questions = normalize_json_values(json_data)

        # Generate PDF
        generate_mcq_pdf(normalized_questions, output_filename)
        print(f"PDF generated successfully: {output_filename}")

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {str(e)}")
        print("Position of error:", e.pos)
        print("Line number:", e.lineno)
        print("Column number:", e.colno)
    except Exception as e:
        print(e)
        print(f"Error processing questions: {str(e)}")


if __name__ == "__main__":
    # Clean the JSON string before processing
    randomDate=str(uuid.uuid4())[:4]
    output_filename=f'session_2_{randomDate}.pdf'
    main(output_filename=output_filename)
