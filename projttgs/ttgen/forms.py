from django.forms import ModelForm
from. models import *
from django import forms


class RoomForm(ModelForm):
    class Meta:
        model = Room
        fields = ['r_number', 'seating_capacity', 'room_type']
        labels = {
            "r_number": "Room ID",
            "seating_capacity": "Capacity",
            "room_type": "Room Type"
        }
        widgets = {
            "room_type": forms.Select(choices=[
                ('Lecture Hall', 'Lecture Hall'),
                ('Lab', 'Lab'),
                ('Seminar Room', 'Seminar Room'),
            ])
        }


class InstructorForm(ModelForm):
    class Meta:
        model = Instructor
        fields = ['uid', 'name']
        labels = {
            "uid": "Teacher UID",
            "name": "Full Name"
        }




class MeetingTimeForm(ModelForm):
    class Meta:
        model = MeetingTime
        fields = ['pid', 'time', 'day']
        labels = {
            "pid": "Meeting ID",
            "time": "Time Slot",
            "day": "Day of Week"
        }
        widgets = {
            'pid': forms.TextInput(),
            'time': forms.Select(choices=[
                ('1', 'Slot 1'),
                ('2', 'Slot 2'),
                ('3', 'Slot 3'),
                ('4', 'Slot 4'),
                ('5', 'Slot 5'),
                ('6', 'Slot 6'),
                ('7', 'Slot 7'),
                ('8', 'Slot 8'),
            ]),
            'day': forms.Select()
        }



class CourseForm(ModelForm):
    class Meta:
        model = Course
        fields = [
            'course_number',
            'course_name',
            'max_numb_students',
            'room_required',
            'time',
            'instructors'
        ]
        labels = {
            "course_number": "Course ID",
            "course_name": "Course Name",
            "max_numb_students": "Max Students",
            "room_required": "Required Room Type",
            "time": "Time Slot Count",
            "instructors": "Assigned Teachers"
        }
        widgets = {
            "room_required": forms.Select(choices=[
                ('Lecture Hall', 'Lecture Hall'),
                ('Lab', 'Lab'),
                ('Seminar Room', 'Seminar Room'),
            ]),

            "time": forms.Select(choices=[
                ('1', '1 Hour'),
                ('2', '2 Hours'),
                ('3', '3 Hours'),
                ('4', '4 Hours'),
            ]),

            "instructors": forms.SelectMultiple(),
        }



# class DepartmentForm(ModelForm):
#     class Meta:
#         model = Department
#         fields = ['dept_name', 'courses']
#         labels = {
#             "dept_name": "Department Name",
#             "courses": "Corresponding Courses"
#         }
class DepartmentForm(ModelForm):
    class Meta:
        model = Department
        fields = ['dept_name', 'courses']
        labels = {
            "dept_name": "Department Name",
            "courses": "Courses Offered"
        }
        widgets = {
            "courses": forms.SelectMultiple()
        }



# class SectionForm(ModelForm):
#     class Meta:
#         model = Section
#         fields = ['section_id', 'department', 'num_class_in_week']
#         labels = {
#             "section_id": "Section ID",
#             "department": "Corresponding Department",
#             "num_class_in_week": "Classes Per Week"
#         }
class SectionForm(ModelForm):
    class Meta:
        model = Section
        fields = ['section_id', 'department', 'num_class_in_week']
        labels = {
            "section_id": "Section ID",
            "department": "Department",
            "num_class_in_week": "Classes Per Week"
        }

