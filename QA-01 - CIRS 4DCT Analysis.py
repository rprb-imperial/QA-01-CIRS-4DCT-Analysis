######################################################################################################################################
#
#   SCRIPT CODE: QA-01
#
#   SCRIPT TITLE: CIRS 4DCT Analysis
#
#   VERSION: 1.0
#
#   ORIGINAL SCRIPT WRITTEN BY:  Robert Richardson/Oliver Steel
#
#   DESCRIPTION & VERSION HISTORY:
#
#	v1.0 (RR/OS) Contours the tumour as an ROI on each phase of a selected 4DCT scan of the CIRS phantom and assess the centre of mass (CoM) 
#	motion and the volume as a function of the 4DCT phase. Saves result to .txt file and creates a plot which are saved to the S:drive and uploads
#	QA results to QATrack.
#
#                   _____________________________________________________________________________
#                           
#                           SCRIPT VALIDATION DATE IN RAYSTATION SHOULD MATCH FILE DATE
#                   _____________________________________________________________________________
#
######################################################################################################################################
# Add in:
#           Button/Option to rename scans by protocol?  Or adjust the lists to display protocol after and look up from a different list or something?
#           Change drop down to ticks to process multiple images at once?  Will need to add in a for loop
#           Add in pause if no groups to allow groups to be made
#           
#
######################################################################################################################################

from connect import *
import sys, datetime
#For plotting data
import matplotlib.pyplot as plt
#For QATrack
import requests
import base64
# Retrieve the path to RayStation.exe (This will only work if the script is run from within RayStation)
script_path = System.IO.Path.GetDirectoryName(sys.argv[0])
path = script_path.rsplit('\\',1)[0]
sys.path.append(path)

#--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Import windows forms
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
from System.Windows.Forms import Application, Form, Label, ComboBox,CheckBox, TextBox, Button, MessageBox, RadioButton, BorderStyle, FormBorderStyle, PictureBox
from System.Drawing import Point, Size,Font,FontStyle, Color

# Ensures that a patient/plan is opened
try:
    examination = get_current("Examination")
except:#Integrity Checks if no patient/plan open
    MessageBox.Show("Ensure a Patient/Plan is open", "Error")
    sys.exit()
patient = get_current("Patient")
case = get_current("Case")
case_name = case.CaseName
patient_name = patient.Name
patient_id = patient.PatientID    
exam_name = examination.Name
structure_set = case.PatientModel.StructureSets[exam_name]
db = get_current("PatientDB")

#--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Generates a list of all exam groups
exam_list_array = []
num_exams = patient.Cases[case_name].Examinations.Count 
for i in range(num_exams):
    exam_list_array.append(patient.Cases[case_name].Examinations[i].Name)

# Generates a list of all exam groups
exam_group_list_array = ["ALL"]
num_exam_groups = patient.Cases[case_name].ExaminationGroups.Count 
for i in range(num_exam_groups):
    exam_group_list_array.append(patient.Cases[case_name].ExaminationGroups[i].Name)

#--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Pop up to select which exam group to run script on
class exam_group_list(Form):
    def __init__(self, plan):
        form_height = 150
        form_width = 300
        self.Size = Size(form_width,form_height)
        self.BackColor = Color.FromArgb(60, 60, 60)
        self.Text = 'Select Exam Group'        
        button_continue = Button()
        button_continue.Text = 'Continue'
        # button_continue.Font = Font("Calibri", 12,FontStyle.Bold)
        button_continue.BackColor = Color.LightGray
        button_continue.AutoSize = True
        button_continue.Location = Point(15, 60)
        button_continue.Click += self.button_continue_clicked
        self.Controls.Add(button_continue)        
        button_exit = Button()
        button_exit.Text = 'Exit'
        # button_exit.Font = Font("Calibri", 12,FontStyle.Bold)
        button_exit.BackColor = Color.LightGray
        button_exit.AutoSize = True
        button_exit.Location = Point(100, 60)
        button_exit.Click += self.button_exit_clicked
        self.Controls.Add(button_exit)
        self.combobox_exam_group_name = ComboBox()
        self.combobox_exam_group_name.Location = Point(15,20)
        self.combobox_exam_group_name.Size = Size(210,35)
        self.combobox_exam_group_name.DataSource = exam_group_list_array
        self.Controls.Add(self.combobox_exam_group_name)        
    def button_continue_clicked(self, sender, event):
        self.end_script = 'N'
        self.exam_group_name = self.combobox_exam_group_name.Text
        self.Close()
    def button_exit_clicked(self, sender, event):
        self.end_script = 'Y'
        self.Close()

exam_group_list = exam_group_list(Form)
Application.Run(exam_group_list)
end_script = exam_group_list.end_script 
exam_group_name = exam_group_list.exam_group_name
# Checks if Exit was selected from form
if exam_group_list.end_script == 'Y':
    sys.exit()

#--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Cycles through each image in the group
if exam_group_name == "ALL":
    exam_group_list_array.remove("ALL")
    for i in range(len(exam_group_list_array)):
        exam_group_name = exam_group_list_array[i]
        #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # Number of images in selected exam group
        num_images_in_group = patient.Cases[case_name].ExaminationGroups[exam_group_name].Items.Count
        patient_name = patient_name.replace('^','_')
        results = ["Patient:" + patient_name + ",Case:" + case_name + "\nExam,x (SAG - L/R),y (COR - A/P),z (AX - S/I),Vol. (cc)"]
        x_coords = []
        x_coords_cor = []
        y_coords = []
        y_coords_cor = []
        z_coords = []
        z_coords_cor = []
        exam_names = []
        volumes = []
        # Gets initial structure set data
        roi_cont = [r.OfRoi.Name for r in structure_set.RoiGeometries if r.PrimaryShape != None]
        roi_not_cont = [r.OfRoi.Name for r in structure_set.RoiGeometries if r.PrimaryShape == None]
        for i in range(num_images_in_group):
            current_exam = patient.Cases[case_name].ExaminationGroups[exam_group_name].Items[i].Examination.Name
            exam_names.append(current_exam)
            current_exam_id = patient.Cases[case_name].ExaminationGroups[exam_group_name].Items[i].Examination
            # Checks if required ROIs are already in place
            structure_set = case.PatientModel.StructureSets[current_exam]
            roi_cont = [r.OfRoi.Name for r in structure_set.RoiGeometries if r.PrimaryShape != None]
            roi_not_cont = [r.OfRoi.Name for r in structure_set.RoiGeometries if r.PrimaryShape == None]    
            if 'QA_Thresh' in roi_cont or 'QA_Thresh' in roi_not_cont:
                try:
                    case.PatientModel.RegionsOfInterest['QA_Thresh'].DeleteRoi()
                except:
                    MessageBox.Show("Issues with ROI QA_Thresh")
                    sys.exit()
            if "TARGET_" + current_exam in roi_cont or "TARGET_" + current_exam in roi_not_cont:
                try:
                    case.PatientModel.RegionsOfInterest["TARGET_" + current_exam].DeleteRoi()        
                except:
                    MessageBox.Show("Issues with ROI TARGET_" + current_exam)
                    sys.exit()
            # Adds a focus ROI for thresholding 
            template_name = 'zzzQA_CIRS'
            tpm = db.LoadTemplatePatientModel(templateName = template_name)
            case.PatientModel.CreateStructuresFromTemplate(SourceTemplate=tpm, SourceExaminationName="CT 10", SourceRoiNames=["QA_Thresh"], SourcePoiNames=[], AssociateStructuresByName=True, TargetExamination=current_exam_id, InitializationOption="AlignImageCenters")
            tpm.Unload()
            # Thresholds IGRT Insert
            with CompositeAction('Gray level threshold (TARGET, Image set: CT 3)'):
                retval_0 = case.PatientModel.CreateRoi(Name="TARGET_" + current_exam, Color="Green", Type="Organ", TissueName=None, RbeCellTypeName=None, RoiMaterial=None)
                retval_0.GrayLevelThreshold(Examination=current_exam_id, LowThreshold=-500, HighThreshold=2000, PetUnit="", CbctUnit=None, BoundingBox=None)
            with CompositeAction('ROI algebra (TARGET)'):
              case.PatientModel.RegionsOfInterest['TARGET_' + current_exam].CreateAlgebraGeometry(Examination=current_exam_id, Algorithm="Auto", ExpressionA={ 'Operation': "Intersection", 'SourceRoiNames': ["QA_Thresh", "TARGET_" + current_exam], 'MarginSettings': { 'Type': "Expand", 'Superior': 0, 'Inferior': 0, 'Anterior': 0, 'Posterior': 0, 'Right': 0, 'Left': 0 } }, ExpressionB={ 'Operation': "Union", 'SourceRoiNames': [], 'MarginSettings': { 'Type': "Expand", 'Superior': 0, 'Inferior': 0, 'Anterior': 0, 'Posterior': 0, 'Right': 0, 'Left': 0 } }, ResultOperation="None", ResultMarginSettings={ 'Type': "Expand", 'Superior': 0, 'Inferior': 0, 'Anterior': 0, 'Posterior': 0, 'Right': 0, 'Left': 0 })  
            # Gets CoM Co-Ordinates and volume information
            com_coord = patient.Cases[case_name].PatientModel.StructureSets[current_exam].RoiGeometries["TARGET_" + current_exam].GetCenterOfRoi()
            x = com_coord.x
            x_coords.append(x)
            y = com_coord.y
            y_coords.append(y)    
            z = com_coord.z
            z_coords.append(z)    
            vol = patient.Cases[case_name].PatientModel.StructureSets[current_exam].RoiGeometries["TARGET_" + current_exam].GetRoiVolume()

            volumes.append(round(vol,2))
            results.append(str(exam_group_name) + "," + str(current_exam) +","+ str(round(x,2)) +","+ str(round(y,2)) +","+ str(round(z,2))+","+ str(round(vol,2)))
            patient.Cases[case_name].PatientModel.RegionsOfInterest["TARGET_" + current_exam].DeleteRoi
        #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # Corrects COM co-ordinates to be relative to first image (should be 0% phase)
        for i in range(len(x_coords)):
            x_coords_cor.append(round((x_coords[i] - x_coords[0]),2))
            y_coords_cor.append(round((y_coords[i] - y_coords[0]),2))
            z_coords_cor.append(round((z_coords[i] - z_coords[0]),2))
        fig, axs = plt.subplots(4)
        axs[0].plot(exam_names, x_coords_cor, color = 'red', marker = 'o', linestyle = 'solid')
        axs[1].plot(exam_names, y_coords_cor, color = 'green', marker = 'o', linestyle = 'solid')
        axs[2].plot(exam_names, z_coords_cor, color = 'blue', marker = 'o', linestyle = 'solid')
        axs[3].plot(exam_names, volumes, color = 'black', marker = 'o', linestyle = 'solid')
        axs[0].set(xlabel='Phase',ylabel='Dist. from 0% Pos. (cm)',title='Target CoM Pos. Vs. 4D Phase (Sag L/R)')
        axs[1].set(xlabel='Phase',ylabel='Dist. from 0% Pos. (cm)',title='Target CoM Pos. Vs. 4D Phase (Cor A/P)')
        axs[2].set(xlabel='Phase',ylabel='Dist. from 0% Pos. (cm)',title='Target CoM Pos. Vs. 4D Phase (Ax S/I)')
        axs[3].set(xlabel='Phase',ylabel='Vol. (cc)',title='Target Vol. Vs. 4D Phase')
        plt.show()
        #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # Saves Results
        today = datetime.datetime.now()
        date_save = str( "{:%y%m%d}".format(today) + "_" +"{:%H%M%S}".format(today))
        base_drive = 'S:\Cancer Services\Radiotherapy cx + hh\_Treatment Data\_RAYSTATION_Exports\QA_SCRIPTS' + '\\'
        base_name = "[" + date_save +"]_QA-1_CIRS_Analysis"
        file_name = base_drive + '\\' + base_name
        fig.savefig(file_name +'_PLOT.png')
        with open(file_name + '.txt', 'w') as f:
            for i in range(len(results)):
                f.write(str(results[i]) + '\n')
        MessageBox.Show("Data saved to:  " + base_drive)           

else:
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # Number of images in selected exam group
    num_images_in_group = patient.Cases[case_name].ExaminationGroups[exam_group_name].Items.Count
    patient_name = patient_name.replace('^','_')
    results = ["Patient:" + patient_name + ",Case:" + case_name + "\nExam,x (SAG - L/R),y (COR - A/P),z (AX - S/I),Vol. (cc)"]
    x_coords = []
    x_coords_cor = []
    y_coords = []
    y_coords_cor = []
    z_coords = []
    z_coords_cor = []
    exam_names = []
    volumes = []
    # Gets initial structure set data
    roi_cont = [r.OfRoi.Name for r in structure_set.RoiGeometries if r.PrimaryShape != None]
    roi_not_cont = [r.OfRoi.Name for r in structure_set.RoiGeometries if r.PrimaryShape == None]
    for i in range(num_images_in_group):
        current_exam = patient.Cases[case_name].ExaminationGroups[exam_group_name].Items[i].Examination.Name
        exam_names.append(current_exam)
        current_exam_id = patient.Cases[case_name].ExaminationGroups[exam_group_name].Items[i].Examination
        # Checks if required ROIs are already in place
        structure_set = case.PatientModel.StructureSets[current_exam]
        roi_cont = [r.OfRoi.Name for r in structure_set.RoiGeometries if r.PrimaryShape != None]
        roi_not_cont = [r.OfRoi.Name for r in structure_set.RoiGeometries if r.PrimaryShape == None]    
        if 'QA_Thresh' in roi_cont or 'QA_Thresh' in roi_not_cont:
            try:
                case.PatientModel.RegionsOfInterest['QA_Thresh'].DeleteRoi()
            except:
                MessageBox.Show("Issues with ROI QA_Thresh")
                sys.exit()
        if "TARGET_" + current_exam in roi_cont or "TARGET_" + current_exam in roi_not_cont:
            try:
                case.PatientModel.RegionsOfInterest["TARGET_" + current_exam].DeleteRoi()        
            except:
                MessageBox.Show("Issues with ROI TARGET_" + current_exam)
                sys.exit()
        # Adds a focus ROI for thresholding 
        template_name = 'zzzQA_CIRS'
        tpm = db.LoadTemplatePatientModel(templateName = template_name)
        case.PatientModel.CreateStructuresFromTemplate(SourceTemplate=tpm, SourceExaminationName="CT 10", SourceRoiNames=["QA_Thresh"], SourcePoiNames=[], AssociateStructuresByName=True, TargetExamination=current_exam_id, InitializationOption="AlignImageCenters")
        tpm.Unload()
        # Thresholds IGRT Insert
        with CompositeAction('Gray level threshold (TARGET, Image set: CT 3)'):
            retval_0 = case.PatientModel.CreateRoi(Name="TARGET_" + current_exam, Color="Green", Type="Organ", TissueName=None, RbeCellTypeName=None, RoiMaterial=None)
            retval_0.GrayLevelThreshold(Examination=current_exam_id, LowThreshold=-500, HighThreshold=2000, PetUnit="", CbctUnit=None, BoundingBox=None)
        with CompositeAction('ROI algebra (TARGET)'):
          case.PatientModel.RegionsOfInterest['TARGET_' + current_exam].CreateAlgebraGeometry(Examination=current_exam_id, Algorithm="Auto", ExpressionA={ 'Operation': "Intersection", 'SourceRoiNames': ["QA_Thresh", "TARGET_" + current_exam], 'MarginSettings': { 'Type': "Expand", 'Superior': 0, 'Inferior': 0, 'Anterior': 0, 'Posterior': 0, 'Right': 0, 'Left': 0 } }, ExpressionB={ 'Operation': "Union", 'SourceRoiNames': [], 'MarginSettings': { 'Type': "Expand", 'Superior': 0, 'Inferior': 0, 'Anterior': 0, 'Posterior': 0, 'Right': 0, 'Left': 0 } }, ResultOperation="None", ResultMarginSettings={ 'Type': "Expand", 'Superior': 0, 'Inferior': 0, 'Anterior': 0, 'Posterior': 0, 'Right': 0, 'Left': 0 })  
        # Gets CoM Co-Ordinates and volume information
        com_coord = patient.Cases[case_name].PatientModel.StructureSets[current_exam].RoiGeometries["TARGET_" + current_exam].GetCenterOfRoi()
        x = com_coord.x
        x_coords.append(x)
        y = com_coord.y
        y_coords.append(y)    
        z = com_coord.z
        z_coords.append(z)    
        vol = patient.Cases[case_name].PatientModel.StructureSets[current_exam].RoiGeometries["TARGET_" + current_exam].GetRoiVolume()

        volumes.append(round(vol,2))
        results.append(str(current_exam) +","+ str(round(x,2)) +","+ str(round(y,2)) +","+ str(round(z,2))+","+ str(round(vol,2)))
        patient.Cases[case_name].PatientModel.RegionsOfInterest["TARGET_" + current_exam].DeleteRoi
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # Corrects COM co-ordinates to be relative to first image (should be 0% phase)
    for i in range(len(x_coords)):
        x_coords_cor.append(round((x_coords[i] - x_coords[0]),2))
        y_coords_cor.append(round((y_coords[i] - y_coords[0]),2))
        z_coords_cor.append(round((z_coords[i] - z_coords[0]),2))
    fig, axs = plt.subplots(4)
    axs[0].plot(exam_names, x_coords_cor, color = 'red', marker = 'o', linestyle = 'solid')
    axs[1].plot(exam_names, y_coords_cor, color = 'green', marker = 'o', linestyle = 'solid')
    axs[2].plot(exam_names, z_coords_cor, color = 'blue', marker = 'o', linestyle = 'solid')
    axs[3].plot(exam_names, volumes, color = 'black', marker = 'o', linestyle = 'solid')
    axs[0].set(xlabel='Phase',ylabel='Dist. from 0% Pos. (cm)',title='Target CoM Pos. Vs. 4D Phase (Sag L/R)')
    axs[1].set(xlabel='Phase',ylabel='Dist. from 0% Pos. (cm)',title='Target CoM Pos. Vs. 4D Phase (Cor A/P)')
    axs[2].set(xlabel='Phase',ylabel='Dist. from 0% Pos. (cm)',title='Target CoM Pos. Vs. 4D Phase (Ax S/I)')
    axs[3].set(xlabel='Phase',ylabel='Vol. (cc)',title='Target Vol. Vs. 4D Phase')
    #plt.show()
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # Saves Results
    today = datetime.datetime.now()
    date_save = str( "{:%y%m%d}".format(today) + "_" +"{:%H%M%S}".format(today))
    base_drive = 'S:\Cancer Services\Radiotherapy cx + hh\_Treatment Data\_RAYSTATION_Exports\QA_SCRIPTS' + '\\'
    base_name = "[" + date_save +"]_QA-1_CIRS_Analysis"
    file_name = base_drive + '\\' + base_name
    fig.savefig(file_name +'_PLOT.png')
    with open(file_name + '.txt', 'w') as f:
        for i in range(len(results)):
            f.write(str(results[i]) + '\n')        
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    class upload_qat(Form):
        def __init__(self, plan):
            form_height = 200
            form_width = 800
            self.Size = Size (form_width,form_height)
            self.BackColor = Color.FromArgb(60, 60, 60)  

            label = Label()
            label.Text = "Data saved to:  "
            label.Location = Point(15, 15)
            label.ForeColor = Color.LightBlue
            label.AutoSize = True
            self.Controls.Add(label) 
            label = Label()
            label.Text = base_drive
            label.Location = Point(15, 40)
            label.ForeColor = Color.Yellow
            label.Height = 20
            label.Width = form_width
            self.Controls.Add(label)             

            label = Label()
            label.Text = 'Upload to QATrack+ ?'
            label.Location = Point(15, 80)
            label.ForeColor = Color.LightBlue
            label.AutoSize = True
            self.Controls.Add(label)      
            button = Button()
            button.Text = 'Yes - Trace [1]'
            button.BackColor = Color.FromArgb(179, 255, 179)
            button.AutoSize = True
            button.Location = Point(15, 100)
            button.Click += self.button_yes1_clicked
            self.Controls.Add(button)        
            button = Button()
            button = Button()
            button.Text = 'Yes - Trace [2]'
            button.BackColor = Color.FromArgb(179, 255, 179)
            button.AutoSize = True
            button.Location = Point(120, 100)
            button.Click += self.button_yes2_clicked
            self.Controls.Add(button)        
            button = Button()
            button.Text = 'No'
            button.BackColor = Color.FromArgb(255, 102, 102)
            button.AutoSize = True
            button.Location = Point(240, 100)
            button.Click += self.button_no_clicked
            self.Controls.Add(button)        
        def button_yes1_clicked(self, sender, event):
            self.end_script = 'N'
            self.qat_upload = 'Y'
            self.trace_number = 1         
            self.Close()
        def button_yes2_clicked(self, sender, event):
            self.end_script = 'N'
            self.qat_upload = 'Y'
            self.trace_number = 2 
            self.Close()            
        def button_no_clicked(self, sender, event):
            self.end_script = 'Y'
            self.qat_upload2 = 'Y'      
            self.Close()

    upload_qat = upload_qat(Form)
    Application.Run(upload_qat)
    end_script = upload_qat.end_script 
    
    trace = upload_qat.trace_number
    upload_qat = upload_qat.qat_upload
    # Checks if Exit was selected from form
    if end_script == 'Y':
        sys.exit()
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    if upload_qat == 'N':        
        MessageBox.Show("Data saved to:  " + base_drive)    
    if upload_qat == 'Y':
        amp_lr_act = max(x_coords_cor) - min(x_coords_cor)
        amp_ap_act = max(y_coords_cor) - min(y_coords_cor)
        amp_si_act = max(z_coords_cor) - min(z_coords_cor)
        # Uploads to QATrack+
        root = "http://10.157.79.80/api"
        # Dirctly provide API token
        token = "e6ed748b207fcf1b07cd7c0c22264abb14115922"
        headers = {"Authorization": "Token %s" % token}
        # Machine/test to have data added into
        unit_name = "CT1 (Siemens)"
        if trace == 1:
            test_list_name = "CT 03 - 4DCT QC [1] (Slow & Deep)"
            amp_lr_exp = 0.5 * 2
            amp_ap_exp = 0.5 * 2
            amp_si_exp = 1.5 * 2           
            
        if trace == 2:          
            test_list_name = "CT 03 - 4DCT QC [2] (Fast & Shallow)"
            amp_lr_exp = 0.25 * 2
            amp_ap_exp = 0.25 * 2
            amp_si_exp = 0.25 * 2
            
        url = root + '/qa/unittestcollections/?unit__name__icontains=%s&test_list__name__icontains=%s' % (unit_name, test_list_name)
        resp = requests.get(url, headers=headers)
        utc_url = resp.json()['results'][0]['url']
        
        # prepare the data to submit to the API. Binary files need to be base64 encoded before posting!
        data = {
            'unit_test_collection': utc_url,
            'work_started': "{:%Y-%m-%d}".format(today)+" "+ "{:%H:%M}".format(today),
            'work_completed': "{:%Y-%m-%d}".format(today)+" "+ "{:%H:%M}".format(today),
            'tests': {
                'us_name': {'value': "TEST"}, # comment is optional
                'ct4d_amp_lr': {'value': amp_lr_act}, # comment is optional        
                'ct4d_amp_ap': {'value': amp_ap_act}, # comment is optional     
                'ct4d_amp_si': {'value': amp_si_act}, # comment is optional    
                'ct4d_amp_lr_exp': {'value': amp_lr_exp}, # comment is optional        
                'ct4d_amp_ap_exp': {'value': amp_ap_exp}, # comment is optional     
                'ct4d_amp_si_exp': {'value': amp_si_exp}, # comment is optional     
                # '4D QA Upload': {  #Name of upload test
                # 'filename': '[240410_115945]_QA-1_CIRS_Analysis_PLOT', # path to file
                # 'value': base64.b64encode(open("S:\Cancer Services\Radiotherapy cx + hh\_Treatment Data\_RAYSTATION_Exports\QA_SCRIPTS\[240410_115945]_QA-1_CIRS_Analysis_PLOT.png", 'rb').read()).decode(),
                # 'encoding': 'base64' 
                #},
    },
            'attachments': []  # optional
        }
        # send our data to the server
        resp = requests.post(root + "/qa/testlistinstances/", json=data, headers=headers)  
        MessageBox.Show("Data saved to QATrack+ and " + "\n" + "\n" + "Data saved to:  " + base_drive)
        
# data = {
#     'unit_test_collection': utc_url,
#     'work_started': "2018-09-19 10:00",
#     'work_completed': "2018-09-19 10:30",
#     'tests': {
#         'us_name': {'value': "TEST", 'comment': "a"}, # comment is optional
#         'image1_x': {'value': x_coords_cor[0], 'comment': "a"}, # comment is optional        
#         'image2_x': {'value': x_coords_cor[1], 'comment': "a"}, # comment is optional     
#         'image3_x': {'value': x_coords_cor[2], 'comment': "a"}, # comment is optional     
#         'image4_x': {'value': x_coords_cor[3], 'comment': "a"}, # comment is optional     
#         'image5_x': {'value': x_coords_cor[4], 'comment': "a"}, # comment is optional     
#         'image6_x': {'value': x_coords_cor[5], 'comment': "a"}, # comment is optional     
#         'image7_x': {'value': x_coords_cor[6], 'comment': "a"}, # comment is optional 
#         'image8_x': {'value': x_coords_cor[7], 'comment': "a"}, # comment is optional     
#         'image9_x': {'value': x_coords_cor[8], 'comment': "a"}, # comment is optional     
#         'image10_x': {'value': int(x_coords_cor[9]), 'comment': ""}, # comment is optional
#         '4D QA Upload': {  #Name of upload test
#             'filename': '[230919 _ 1738]_QA-1_-_CIRS_Analysis_PLOT.png', # path to file
#             'value': base64.b64encode(open("S:\Cancer Services\Radiotherapy cx + hh\_Treatment Data\_RAYSTATION_Exports\QA_SCRIPTS\[230919 _ 1738]_QA-1_-_CIRS_Analysis_PLOT.png", 'rb').read()).decode(),  'encoding': 'base64'      },
#     },
#     'attachments': []  # optional        
        
#         MessageBox.Show("Data saved to QATrack+")

