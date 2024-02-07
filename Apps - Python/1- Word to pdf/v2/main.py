import os
import tempfile
import openpyxl
from docx2pdf import convert
from docxtpl import DocxTemplate

data = {}

def read_data(file_path, key_col, data_col):
    global data

    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active
    keys = []
    for cellObj in sheet[key_col]:
        val = str(cellObj.value)
        if val != 'None': 
            keys.append(val)

    for idx, cellObj in enumerate(sheet[data_col]):
        val = str(cellObj.value)
        if val == 'None': 
            continue
        key = keys[idx]
        if key in data:
            data[key].append(val)
        else:
            data[key] = [val]

def format_data(sz):
    for key in data:
        while len(data[key]) < sz:
            data[key].append(data[key][-1])

def run(excel_files, word_file, key_column_var, value_column_var, progress_var, output_folder):
    file_names = []
    progrees = 100 / (len(excel_files) * 2)
    print(progrees)
    for idx, file_path in enumerate(excel_files):
        file_name = file_path.split("/")[-1].split(".")[0]
        file_names.append(file_name)
        read_data(file_path, key_column_var, value_column_var)
        format_data(idx + 1)
        progress_var["value"] += progrees
        progress_var.update_idletasks()

    write_data(file_names, word_file, progress_var, output_folder)

def write_data(pdf_names, word_file, progress_var, output_folder):
    progrees = 100 / (len(pdf_names) * 2)
    doc = DocxTemplate(word_file)
    
    for idx, pdf_name in enumerate(pdf_names):        
        context = {}
        for key in data:
            context[key] = data[key][idx]

        doc.render(context)
        
        temp_file_path = save_as_temp_file(doc)
        pdf = pdf_name + ".pdf"

        if idx == 0:
            # output_folder = os.path.join(os.getcwd(), 'output')
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)

        convert(temp_file_path, os.path.join(output_folder, pdf))
        # os.remove(os.path.join(".output.docx"))

        progress_var["value"] += progrees
        progress_var.update_idletasks()

def save_as_temp_file(doc):
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, "output.docx")
    doc.save(temp_file_path)
    return temp_file_path

if __name__ == "__main__":
    run()