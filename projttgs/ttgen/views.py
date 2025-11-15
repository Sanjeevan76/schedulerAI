# COde for Genetic Algorithm
# It have : 1. Model data loading -> models.py
#           2. Genetic Algorithm components
#           3. Fitness Evaluation
#           4. Django views for CRUD operations
#           5. PDF export -> render.py
#           6. FOrm submissions and rendering -> forms.py


from django.http import request
from django.shortcuts import render, redirect
from . forms import *
from .models import *
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required
from .render import Render
from django.views.generic import View


POPULATION_SIZE = 9 # no.of candidates
NUMB_OF_ELITE_SCHEDULES = 1 # top schedules without modification
TOURNAMENT_SELECTION_SIZE = 3 # candidate comprting for selection
MUTATION_RATE = 0.05 # random variability

# THis class have all database objecrs -> rooms, instructors, courses, meeting time, department
class Data:
    def __init__(self):
        self._rooms = Room.objects.all()
        self._meetingTimes = MeetingTime.objects.all()
        self._instructors = Instructor.objects.all()
        self._courses = Course.objects.all()
        self._depts = Department.objects.all()

    def get_rooms(self): return self._rooms

    def get_instructors(self): return self._instructors

    def get_courses(self): return self._courses

    def get_depts(self): return self._depts

    def get_meetingTimes(self): return self._meetingTimes

# THis class represt one complete possible timetable
# _classes -> list of all class slots
# _fitness -> quality score
# _numberofConflicts -> scheduling conflicts
# _isFitnessChanged -> recalulation jab jaruri ho
class Schedule:
    def __init__(self):
        self._data = data
        self._classes = []
        self._numberOfConflicts = 0
        self._fitness = -1
        self._classNumb = 0
        self._isFitnessChanged = True

    def get_classes(self):
        self._isFitnessChanged = True
        return self._classes

    def get_numbOfConflicts(self): return self._numberOfConflicts

    def get_fitness(self):
        if self._isFitnessChanged:
            self._fitness = self.calculate_fitness()
            self._isFitnessChanged = False
        return self._fitness

    # Randomly generate a timing by assigning meeting time, room, instructor
    def initialize(self):
        sections = Section.objects.all()
        for section in sections:
            dept = section.department
            n = section.num_class_in_week
            if n <= len(MeetingTime.objects.all()):
                courses = dept.courses.all()
                for course in courses:
                    for i in range(n // len(courses)):
                        crs_inst = course.instructors.all()
                        newClass = Class(self._classNumb, dept, section.section_id, course)
                        self._classNumb += 1
                        newClass.set_meetingTime(data.get_meetingTimes()[rnd.randrange(0, len(MeetingTime.objects.all()))])
                        newClass.set_room(data.get_rooms()[rnd.randrange(0, len(data.get_rooms()))])
                        newClass.set_instructor(crs_inst[rnd.randrange(0, len(crs_inst))])
                        self._classes.append(newClass)
            else:
                n = len(MeetingTime.objects.all())
                courses = dept.courses.all()
                for course in courses:
                    for i in range(n // len(courses)):
                        crs_inst = course.instructors.all()
                        newClass = Class(self._classNumb, dept, section.section_id, course)
                        self._classNumb += 1
                        newClass.set_meetingTime(data.get_meetingTimes()[rnd.randrange(0, len(MeetingTime.objects.all()))])
                        newClass.set_room(data.get_rooms()[rnd.randrange(0, len(data.get_rooms()))])
                        newClass.set_instructor(crs_inst[rnd.randrange(0, len(crs_inst))])
                        self._classes.append(newClass)

        return self

    # check quality of the timetable
    # A conflict is counted if : 
    #   1. Room capacity < required seats
    #   2. Two classes in the same room at the same time
    #   3. Instructor is double-booked
    #   4. Two sections clash with the same meeting time
    def calculate_fitness(self):
        self._numberOfConflicts = 0
        classes = self.get_classes()
        for i in range(len(classes)):
            if classes[i].room.seating_capacity < int(classes[i].course.max_numb_students):
                self._numberOfConflicts += 1
            for j in range(len(classes)):
                if j >= i:
                    if (classes[i].meeting_time == classes[j].meeting_time) and \
                            (classes[i].section_id != classes[j].section_id) and (classes[i].section == classes[j].section):
                        if classes[i].room == classes[j].room:
                            self._numberOfConflicts += 1
                        if classes[i].instructor == classes[j].instructor:
                            self._numberOfConflicts += 1
        return 1 / (1.0 * self._numberOfConflicts + 1) # fitness = 1 / (1 + number_of_conflicts) -> fewer conflicts -> higher fitness -> 1.0 for perfect timetable

# Represents a collection of schedule
class Population:
    def __init__(self, size):
        self._size = size
        self._data = data
        self._schedules = [Schedule().initialize() for i in range(size)] #new population is generated at the start.

    def get_schedules(self):
        return self._schedules

# genetic algorithm class
class GeneticAlgorithm:
    def evolve(self, population):
         # Crossover then mutation
        return self._mutate_population(self._crossover_population(population))
     # Create new population from crossover
    def _crossover_population(self, pop):
        crossover_pop = Population(0)
        # Add elite schedules unchanged
        for i in range(NUMB_OF_ELITE_SCHEDULES):
            crossover_pop.get_schedules().append(pop.get_schedules()[i])
         # Perform crossover for remaining schedules
        i = NUMB_OF_ELITE_SCHEDULES
        while i < POPULATION_SIZE:
            schedule1 = self._select_tournament_population(pop).get_schedules()[0]
            schedule2 = self._select_tournament_population(pop).get_schedules()[0]
            crossover_pop.get_schedules().append(self._crossover_schedule(schedule1, schedule2))
            i += 1
        return crossover_pop

    def _mutate_population(self, population):
        for i in range(NUMB_OF_ELITE_SCHEDULES, POPULATION_SIZE):
            self._mutate_schedule(population.get_schedules()[i])
        return population

    def _crossover_schedule(self, schedule1, schedule2):
        crossoverSchedule = Schedule().initialize()
        for i in range(0, len(crossoverSchedule.get_classes())):
            if rnd.random() > 0.5: # Two schedules exchange data to produce offspring:
                crossoverSchedule.get_classes()[i] = schedule1.get_classes()[i]
            else:
                crossoverSchedule.get_classes()[i] = schedule2.get_classes()[i]
        return crossoverSchedule

    def _mutate_schedule(self, mutateSchedule): # Randomly changes some class assignments to maintain diversity.
        schedule = Schedule().initialize()
        for i in range(len(mutateSchedule.get_classes())):
            if MUTATION_RATE > rnd.random():
                mutateSchedule.get_classes()[i] = schedule.get_classes()[i]
        return mutateSchedule

    def _select_tournament_population(self, pop): # Random subset of schedules compete; fittest is chosen.
        tournament_pop = Population(0)
        i = 0
        while i < TOURNAMENT_SELECTION_SIZE:
            tournament_pop.get_schedules().append(pop.get_schedules()[rnd.randrange(0, POPULATION_SIZE)])
            i += 1
         # Sort by fitness (descending)
        tournament_pop.get_schedules().sort(key=lambda x: x.get_fitness(), reverse=True)
        return tournament_pop

# Class Object used inside Schedule (NOT database model)
# Represents an individual scheduled class slot.
class Class:
    def __init__(self, id, dept, section, course):
        self.section_id = id
        self.department = dept
        self.course = course
        self.instructor = None
        self.meeting_time = None
        self.room = None
        self.section = section

    def get_id(self): return self.section_id

    def get_dept(self): return self.department

    def get_course(self): return self.course

    def get_instructor(self): return self.instructor

    def get_meetingTime(self): return self.meeting_time

    def get_room(self): return self.room

    def set_instructor(self, instructor): self.instructor = instructor

    def set_meetingTime(self, meetingTime): self.meeting_time = meetingTime

    def set_room(self, room): self.room = room

# Global data object used throughout the GA
data = Data()

# Converts raw schedule objects into human-readable format (dictionary) for rendering in templates
def context_manager(schedule):
    classes = schedule.get_classes()
    context = []
    cls = {}
    for i in range(len(classes)):
        cls["section"] = classes[i].section_id
        cls['dept'] = classes[i].department.dept_name
        cls['course'] = f'{classes[i].course.course_name} ({classes[i].course.course_number}, ' \
                        f'{classes[i].course.max_numb_students}'
        cls['room'] = f'{classes[i].room.r_number} ({classes[i].room.seating_capacity})'
        cls['instructor'] = f'{classes[i].instructor.name} ({classes[i].instructor.uid})'
        cls['meeting_time'] = [classes[i].meeting_time.pid, classes[i].meeting_time.day, classes[i].meeting_time.time]
        context.append(cls)
    return context

# core view that generates the timetable
#Steps:
#Create initial population.
#Sort by fitness.
#Iterate (evolve) until fitness becomes 1.0 (perfect solution).
#Render the result in HTML.
def timetable(request):
    schedule = []
    population = Population(POPULATION_SIZE)
    generation_num = 0
    population.get_schedules().sort(key=lambda x: x.get_fitness(), reverse=True)
    geneticAlgorithm = GeneticAlgorithm()

    while population.get_schedules()[0].get_fitness() != 1.0:
        generation_num += 1
        print("Generation #: " + str(generation_num) +
              " Fittest: " + str(population.get_schedules()[0].get_fitness()))
         # Evolve population
        population = geneticAlgorithm.evolve(population)
        population.get_schedules().sort(key=lambda x: x.get_fitness(), reverse=True)
        schedule = population.get_schedules()[0].get_classes()

    # Days to display in timetable
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    # Get UNIQUE TIME SLOTS ONLY
    unique_times = list(
        MeetingTime.objects.values_list("time", flat=True).distinct()
    )

    return render(request, 'gentimetable.html', {
        'schedule': schedule,
        'sections': Section.objects.all(),
        'times': unique_times,
        'days': days
    })



############################################################################


def index(request):
    return render(request, 'index.html', {})


def about(request):
    return render(request, 'aboutus.html', {})


def help(request):
    return render(request, 'help.html', {})


def terms(request):
    return render(request, 'terms.html', {})

# Contact form view that sends email to admin
def contact(request):
    if request.method == 'POST':
        message = request.POST['message']

        send_mail(' Contact',
                  message,
                  settings.EMAIL_HOST_USER,
                  ['studyyou40@gmail.com'], #have to change
                  fail_silently=False)
    return render(request, 'contact.html', {})

#################################################################################
# Admin dashboard view (authentication protected)
@login_required
def admindash(request):
    return render(request, 'admindashboard.html', {})

#################################################################################
# CRUD Views for Courses, Instructors, Rooms, Meeting Times, Departments, Sections
# Each view uses Django ModelForms for input handling
@login_required
def addCourses(request):
    form = CourseForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            return redirect('addCourses')
        else:
            print('Invalid')
    context = {
        'form': form
    }
    return render(request, 'addCourses.html', context)

@login_required
def course_list_view(request):
    context = {
        'courses': Course.objects.all()
    }
    return render(request, 'courseslist.html', context)

@login_required
def delete_course(request, pk):
    crs = Course.objects.filter(pk=pk)
    if request.method == 'POST':
        crs.delete()
        return redirect('editcourse')

#################################################################################
# Instructor CRUD
@login_required
def addInstructor(request):
    form = InstructorForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            return redirect('addInstructors')
    context = {
        'form': form
    }
    return render(request, 'addInstructors.html', context)

@login_required
def inst_list_view(request):
    context = {
        'instructors': Instructor.objects.all()
    }
    return render(request, 'inslist.html', context)

@login_required
def delete_instructor(request, pk):
    inst = Instructor.objects.filter(pk=pk)
    if request.method == 'POST':
        inst.delete()
        return redirect('editinstructor')

#################################################################################
# Room CRUD
@login_required
def addRooms(request):
    form = RoomForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            return redirect('addRooms')
    context = {
        'form': form
    }
    return render(request, 'addRooms.html', context)

@login_required
def room_list(request):
    context = {
        'rooms': Room.objects.all()
    }
    return render(request, 'roomslist.html', context)

@login_required
def delete_room(request, pk):
    rm = Room.objects.filter(pk=pk)
    if request.method == 'POST':
        rm.delete()
        return redirect('editrooms')

#################################################################################
# Meeting Time CRUD
@login_required
def addTimings(request):
    form = MeetingTimeForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            return redirect('addTimings')
        else:
            print('Invalid')
    context = {
        'form': form
    }
    return render(request, 'addTimings.html', context)

@login_required
def meeting_list_view(request):
    context = {
        'meeting_times': MeetingTime.objects.all()
    }
    return render(request, 'mtlist.html', context)

@login_required
def delete_meeting_time(request, pk):
    mt = MeetingTime.objects.filter(pk=pk)
    if request.method == 'POST':
        mt.delete()
        return redirect('editmeetingtime')

#################################################################################
# Department CRUD
@login_required
def addDepts(request):
    form = DepartmentForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            return redirect('addDepts')
    context = {
        'form': form
    }
    return render(request, 'addDepts.html', context)

@login_required
def department_list(request):
    context = {
        'departments': Department.objects.all()
    }
    return render(request, 'deptlist.html', context)

@login_required
def delete_department(request, pk):
    dept = Department.objects.filter(pk=pk)
    if request.method == 'POST':
        dept.delete()
        return redirect('editdepartment')

#################################################################################
# Section CRUD
@login_required
def addSections(request):
    form = SectionForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            return redirect('addSections')
    context = {
        'form': form
    }
    return render(request, 'addSections.html', context)

@login_required
def section_list(request):
    context = {
        'sections': Section.objects.all()
    }
    return render(request, 'seclist.html', context)

@login_required
def delete_section(request, pk):
    sec = Section.objects.filter(pk=pk)
    if request.method == 'POST':
        sec.delete()
        return redirect('editsection')

#################################################################################
# Render simple generate page
@login_required
def generate(request):
    return render(request, 'generate.html', {})

#################################################################################
# PDF Export View
class Pdf(View):
    def get(self, request):
        params = {
            'request': request
        }
        return Render.render('gentimetable.html', params)


