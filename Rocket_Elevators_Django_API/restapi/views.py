import email
from hashlib import new
from pathlib import Path
from django.shortcuts import render
from django.core import serializers
from .serializers import EmployeesSerializer
from .models import Employees
from .models import Users
from rest_framework.decorators import action
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from PIL import Image, ImageDraw
import face_recognition
import os
from os.path import isfile, join
from os import listdir
import shutil

TOLERANCE = 0.5 # Face recognition tolerance: lower means a stricter search algorithm, higher is more loose
from django.conf import settings

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employees.objects.all().order_by('last_name')
    serializer_class = EmployeesSerializer

    # Delete the contents in the media folder
    def clearContents(self):
        for root, dirs, files in os.walk('./media'):
            for f in files:
                os.unlink(os.path.join(root, f))
            for d in dirs:
                shutil.rmtree(os.path.join(root, d))

    # Handles file upload, generates a readable file name, and stores it in the "media" folder
    # @action (detail=False, methods=['post'])
    def uploadFunc(self, request):
        if request.method == 'POST' and request.FILES['myfile']:
            myfile = request.FILES['myfile']
            fs = FileSystemStorage()
            filename = fs.save(myfile.name, myfile)
            return Response(filename, status = status.HTTP_202_ACCEPTED)
        return Response({"failed":"File not accepted"}, status = status.HTTP_400_BAD_REQUEST)

    # Grabs facial landmarks of the uploaded file and returns the json data
    @csrf_exempt
    def obtainFacialKeypoints(self, request):
        if request.method == "POST":            
            employee = Employees()

            # Load the jpg file into a numpy array
            upload = self.uploadFunc(request).data
            data_folder = Path("/home/wevertr/djangoenv/Rocket_Elevators_Django_API/media/")
            file_path = data_folder / upload
            image = face_recognition.load_image_file(file_path)

            # Find all facial features in all the faces in the image
            face_landmarks_list = face_recognition.face_landmarks(image)

            print("I found {} face(s) in this photograph.".format(len(face_landmarks_list)))

            # Create a PIL imagedraw object so we can draw on the picture
            pil_image = Image.fromarray(image)
            d = ImageDraw.Draw(pil_image)

            for face_landmarks in face_landmarks_list:

                # Print the location of each facial feature in this image
                for facial_feature in face_landmarks.keys():
                    print("The {} in this face has the following points: {}".format(facial_feature, face_landmarks[facial_feature]))

                # Let's trace out each facial feature in the image with a line!
                for facial_feature in face_landmarks.keys():
                    d.line(face_landmarks[facial_feature], width=5)

            # Return landmarks list
            employee.facial_keypoints = face_landmarks_list
            return Response(face_landmarks_list, status = status.HTTP_202_ACCEPTED)

    # Runs the face_recognition script on the uploaded image and compares it to the images found in the "positive_images" folder
    # This code will NOT work if the uploaded filename doesn't match the first_name attribute of the employees table
        # To-do: make a catch with a 500 Bad Request httpresponse
        # Saving to media folder not actually 
    @action (detail=False, methods=['post', 'put'])
    def faceDataExistingEmployees(self, request):
        positive_images_dir_path = Path("/home/wevertr/djangoenv/Rocket_Elevators_Django_API/restapi/positive_images/")
        #Obtains all files located in the positive_images directory
        files = [f for f in listdir(positive_images_dir_path) if isfile(join(positive_images_dir_path, f))]
        coaches = []
        fileList_no_ext = []
        for file in files:
            full_path = positive_images_dir_path / file
            file_ndArray = face_recognition.load_image_file(full_path)
            files_no_ext = os.path.splitext(file)[0]
            fileList_no_ext.append(files_no_ext)
            coaches.append(file_ndArray)
        upload = self.uploadFunc(request).data
        data_folder = Path("/home/wevertr/djangoenv/Rocket_Elevators_Django_API/media/")
        file_path = data_folder / upload
        unknownFace = face_recognition.load_image_file(file_path)

        try:
            face_encoding = []
            for c in coaches:
                face_encoding.append(face_recognition.face_encodings(c)[0])
            unknown_face_encoding = face_recognition.face_encodings(unknownFace)[0]
        except IndexError:
            print("I wasn't able to locate any faces in at least one of the images. Check the image files. Aborting...")
            quit()

        known_faces = face_encoding

        # Results is an array of True/False telling if the unknown face matched anyone in the known_faces array
        results = face_recognition.compare_faces(known_faces, unknown_face_encoding, TOLERANCE)
        i = 0
        # Grabs the employee object corresponding to the scanned photo, clears the media folder, and returns the data
        for result in results:
            if result == True:
                selected_coach = Employees.objects.get(first_name = fileList_no_ext[i])
                response = serializers.serialize('python', [selected_coach], ensure_ascii=False)
                self.clearContents()
                encoding = unknown_face_encoding
                return Response([response, encoding], status = status.HTTP_200_OK)
            elif result == False:
                i += 1
            else:
                return Response({"An error has occurred, HTTP-400: BAD REQUEST"}, status = status.HTTP_400_BAD_REQUEST)
        return Response({"Error: Photo does not match existing employees"}, status = status.HTTP_400_BAD_REQUEST)

    # Endpoint for registering a new employee
    @csrf_exempt
    @action (detail=False, methods = ['post'])
    def create_employee(self, request):
        employees = Employees.objects.all()
        employee = Employees()
        user_emails = Users.objects.values_list('email', flat=True)
        user_emails_list = list(user_emails)
        employee_emails = Employees.objects.values_list('email', flat=True)
        employee_emails_list = list(employee_emails)
        submitted_email = request.data['email']
        match = False
        # If the submitted email is not in the emails within the Users table, registration is denied
        # Registration is also denied if submitted email is already registered
        if submitted_email in user_emails_list:
            if submitted_email in employee_emails_list:
                return Response({"Error: Employee email already registered."}, status = status.HTTP_401_UNAUTHORIZED)
            match = True
        else:
            match = False
        upload = self.uploadFunc(request).data
        photo = face_recognition.load_image_file(f"/home/wevertr/djangoenv/Rocket_Elevators_Django_API/media/{upload}")
        encoded = face_recognition.face_encodings(photo)[0]
        
        attributes = {
            'first_name': request.data['first_name'],
            'last_name': request.data['last_name'],
            'title': request.data['title'],
            'email': request.data['email'],
            'facial_keypoints': encoded.tolist()
        }
        setID = employees.count() + 1
        employee.__setattr__('first_name', attributes['first_name'])
        employee.__setattr__('last_name', attributes['last_name'])
        employee.__setattr__('title', attributes['title'])
        employee.__setattr__('email', attributes['email'])
        employee.__setattr__('facial_keypoints', attributes['facial_keypoints'])
        employee.__setattr__('id', setID)
        self.clearContents()
        if match == True:
            employee.save()
            return Response(attributes, status = status.HTTP_201_CREATED)
        else:
            return Response({"Error: Unauthorized access. Check your credentials and try again."}, status = status.HTTP_401_UNAUTHORIZED)
        
