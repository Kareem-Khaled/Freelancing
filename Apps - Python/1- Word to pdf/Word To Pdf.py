from docxtpl import DocxTemplate
from docx2pdf import convert
import openpyxl
import os

def read_data(file_path = "data.xlsx", column_name = "C"):
    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active
    data = []
    for cellObj in sheet[column_name]:
        val = str(cellObj.value)
        data.append(val)

    return data

def run(directory_path = "excel_files"):
    excel_files = [f for f in os.listdir(directory_path) if f.endswith('.xlsx') or f.endswith('.xls')]

    for file_name in excel_files:
        file_path = os.path.join(directory_path, file_name)
        data = read_data(file_path)
        write_data(data, file_name)

def write_data(data, pdf_name, word_file = "form.docx"):
    doc = DocxTemplate(word_file)
    context = {}
    for i in range(0, len(data)):
        context[f"c{i}"] = data[i]

    doc.render(context)
    
    doc.save("output.docx")
    pdf = pdf_name.split(".")[0] + ".pdf"

    output_folder = os.path.join(os.getcwd(), 'output')

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    convert('output.docx', os.path.join(output_folder, pdf))

    os.remove(os.path.join("output.docx"))

if __name__ == "__main__":
    run()