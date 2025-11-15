# COde for Genetic Algorithm
# It have : 1. Model data loading -> models.py
#           2. Genetic Algorithm components
#           3. Fitness Evaluation
#           4. Django views for CRUD operations
#           5. PDF export -> render.py
#           6. Form submissions and rendering -> forms.py

from django.http import request
from django.shortcuts import render, redirect
from .forms import *
from .models import *
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required
from .render import Render
from django.views.generic import View
import random as rnd


# GA Parameters
POPULATION_SIZE = 9              # number of candidate timetables
NUMB_OF_ELITE_SCHEDULES = 1      # elites carried forward without changes
TOURNAMENT_SELECTION_SIZE = 3     # number of candidates competing in selection
MUTATION_RATE = 0.05              # random variation rate


# DATA WRAPPER — loads all DB objects needed for GA
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


# SCHEDULE CLASS — represents one complete timetable
# _classes = list of class slots
# _fitness = scoring of timetable quality
# _numberOfConflicts = detected conflicts
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

    def get_numbOfConflicts(self):
        return self._numberOfConflicts

    def get_fitness(self):
        if self._isFitnessChanged:
            self._fitness = self.calculate_fitness()
            self._isFitnessChanged = False
        return self._fitness

    # Randomly assign meeting time, room, instructor to each required class
    def initialize(self):
        sections = Section.objects.all()
        for section in sections:
            dept = section.department
            n = section.num_class_in_week

            # number of meeting slots
            total_slots = len(MeetingTime.objects.all())
            courses = dept.courses.all()

            repeat = min(n, total_slots) // len(courses)

            for course in courses:
                for _ in range(repeat):
                    crs_inst = course.instructors.all()
                    newClass = Class(self._classNumb, dept, section.section_id, course)
                    self._classNumb += 1

                    newClass.set_meetingTime(
                        data.get_meetingTimes()[rnd.randrange(0, total_slots)]
                    )
                    newClass.set_room(
                        data.get_rooms()[rnd.randrange(0, len(data.get_rooms()))]
                    )
                    newClass.set_instructor(
                        crs_inst[rnd.randrange(0, len(crs_inst))]
                    )

                    self._classes.append(newClass)

        return self

    # FITNESS FUNCTION
    # Conflicts counted:
    # 1. Room capacity < required
    # 2. Room conflict (same room, same time)
    # 3. Instructor conflict (same instructor, same time)
    # 4. Section conflict (same section, same time)
    # fitness = 1 / (1 + conflicts)
    def calculate_fitness(self):
        self._numberOfConflicts = 0
        classes = self.get_classes()

        for i in range(len(classes)):
            # 1. Room capacity insufficient
            try:
                if classes[i].room.seating_capacity < int(classes[i].course.max_numb_students):
                    self._numberOfConflicts += 1
            except:
                self._numberOfConflicts += 1

            for j in range(i + 1, len(classes)):

                same_time = classes[i].meeting_time == classes[j].meeting_time

                # 2. Section conflict
                if same_time and classes[i].section == classes[j].section:
                    self._numberOfConflicts += 1

                # 3. Room conflict
                if same_time and classes[i].room == classes[j].room:
                    if classes[i].section != classes[j].section:
                        self._numberOfConflicts += 1

                # 4. Instructor conflict
                if same_time and classes[i].instructor == classes[j].instructor:
                    self._numberOfConflicts += 1

        return 1 / (1.0 * self._numberOfConflicts + 1)


# POPULATION CLASS — list of candidate timetables
class Population:
    def __init__(self, size):
        self._size = size
        self._data = data
        self._schedules = [Schedule().initialize() for _ in range(size)]

    def get_schedules(self):
        return self._schedules


# GENETIC ALGORITHM
class GeneticAlgorithm:
    def evolve(self, population):
        return self._mutate_population(self._crossover_population(population))

    # CROSSOVER
    def _crossover_population(self, pop):
        crossover_pop = Population(0)

        # Carry forward elite schedule
        for i in range(NUMB_OF_ELITE_SCHEDULES):
            crossover_pop.get_schedules().append(pop.get_schedules()[i])

        # Produce new schedules
        while len(crossover_pop.get_schedules()) < POPULATION_SIZE:
            schedule1 = self._select_tournament_population(pop).get_schedules()[0]
            schedule2 = self._select_tournament_population(pop).get_schedules()[0]
            crossover_pop.get_schedules().append(
                self._crossover_schedule(schedule1, schedule2)
            )

        return crossover_pop

    # MUTATION
    def _mutate_population(self, population):
        for i in range(NUMB_OF_ELITE_SCHEDULES, POPULATION_SIZE):
            self._mutate_schedule(population.get_schedules()[i])
        return population

    def _crossover_schedule(self, schedule1, schedule2):
        crossoverSchedule = Schedule().initialize()
        for i in range(len(crossoverSchedule.get_classes())):
            crossoverSchedule.get_classes()[i] = (
                schedule1.get_classes()[i]
                if rnd.random() > 0.5
                else schedule2.get_classes()[i]
            )
        return crossoverSchedule

    def _mutate_schedule(self, mutateSchedule):
        schedule = Schedule().initialize()
        for i in range(len(mutateSchedule.get_classes())):
            if rnd.random() < MUTATION_RATE:
                mutateSchedule.get_classes()[i] = schedule.get_classes()[i]
        return mutateSchedule

    # TOURNAMENT SELECTION
    def _select_tournament_population(self, pop):
        tournament_pop = Population(0)
        for _ in range(TOURNAMENT_SELECTION_SIZE):
            tournament_pop.get_schedules().append(
                pop.get_schedules()[rnd.randrange(POPULATION_SIZE)]
            )

        tournament_pop.get_schedules().sort(
            key=lambda x: x.get_fitness(), reverse=True
        )
        return tournament_pop



# CLASS OBJECT (NOT A DATABASE MODEL)
# Represents an individual class slot
class Class:
    def __init__(self, id, dept, section, course):
        self.section_id = id
        self.department = dept
        self.course = course
        self.instructor = None
        self.meeting_time = None
        self.room = None
        self.section = section

    def set_instructor(self, instructor): self.instructor = instructor
    def set_meetingTime(self, meetingTime): self.meeting_time = meetingTime
    def set_room(self, room): self.room = room


# GLOBAL DATA OBJECT
data = Data()


# CONTEXT MANAGER — for readable output in HTML
def context_manager(schedule):
    classes = schedule.get_classes()
    context = []
    for cls in classes:
        context.append({
            "section": cls.section_id,
            "dept": cls.department.dept_name,
            "course": f"{cls.course.course_name} ({cls.course.course_number}, {cls.course.max_numb_students})",
            "room": f"{cls.room.r_number} ({cls.room.seating_capacity})",
            "instructor": f"{cls.instructor.name} ({cls.instructor.uid})",
            "meeting_time": [
                cls.meeting_time.pid,
                cls.meeting_time.day,
                cls.meeting_time.time
            ]
        })
    return context


# TIMETABLE GENERATION VIEW

def timetable(request):
    population = Population(POPULATION_SIZE)
    population.get_schedules().sort(key=lambda x: x.get_fitness(), reverse=True)
    geneticAlgorithm = GeneticAlgorithm()
    generation_num = 0

    MAX_GENERATIONS = 600
    FITNESS_THRESHOLD = 0.95
    print("Generation #: " + str(generation_num) +
          " Fittest: " + str(population.get_schedules()[0].get_fitness()))
         # Evolve population

    # Evolution loop
    while population.get_schedules()[0].get_fitness() < FITNESS_THRESHOLD and generation_num < MAX_GENERATIONS:
        generation_num += 1
        population = geneticAlgorithm.evolve(population)
        population.get_schedules().sort(key=lambda x: x.get_fitness(), reverse=True)

    schedule = population.get_schedules()[0].get_classes()

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    unique_times = list(
        MeetingTime.objects.order_by('time').values_list("time", flat=True).distinct()
    )
    print("Generation #: " + str(generation_num) +
          " Fittest: " + str(population.get_schedules()[0].get_fitness()))
    return render(request, 'gentimetable.html', {
        'schedule': schedule,
        'sections': Section.objects.all(),
        'times': unique_times,
        'days': days
    })


# BASIC PAGES
def index(request): return render(request, 'index.html')
def about(request): return render(request, 'aboutus.html')
def help(request): return render(request, 'help.html')
def terms(request): return render(request, 'terms.html')


# CONTACT FORM EMAIL
def contact(request):
    if request.method == 'POST':
        message = request.POST['message']
        send_mail(
            'Contact',
            message,
            settings.EMAIL_HOST_USER,
            ['studyyou40@gmail.com'],
            fail_silently=False
        )
    return render(request, 'contact.html')


# ADMIN DASHBOARD
@login_required
def admindash(request):
    return render(request, 'admindashboard.html')


# COURSE CRUD

@login_required
def addCourses(request):
    form = CourseForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('addCourses')
    return render(request, 'addCourses.html', {'form': form})


@login_required
def course_list_view(request):
    return render(request, 'courseslist.html', {
        'courses': Course.objects.all()
    })


@login_required
def delete_course(request, pk):
    if request.method == 'POST':
        Course.objects.filter(pk=pk).delete()
        return redirect('editcourse')


# INSTRUCTOR CRUD

@login_required
def addInstructor(request):
    form = InstructorForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('addInstructors')
    return render(request, 'addInstructors.html', {'form': form})


@login_required
def inst_list_view(request):
    return render(request, 'inslist.html', {
        'instructors': Instructor.objects.all()
    })


@login_required
def delete_instructor(request, pk):
    if request.method == 'POST':
        Instructor.objects.filter(pk=pk).delete()
        return redirect('editinstructor')



# ROOM CRUD

@login_required
def addRooms(request):
    form = RoomForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('addRooms')
    return render(request, 'addRooms.html', {'form': form})


@login_required
def room_list(request):
    return render(request, 'roomslist.html', {
        'rooms': Room.objects.all()
    })


@login_required
def delete_room(request, pk):
    if request.method == 'POST':
        Room.objects.filter(pk=pk).delete()
        return redirect('editrooms')



# MEETING TIME CRUD

@login_required
def addTimings(request):
    form = MeetingTimeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('addTimings')
    return render(request, 'addTimings.html', {'form': form})


@login_required
def meeting_list_view(request):
    return render(request, 'mtlist.html', {
        'meeting_times': MeetingTime.objects.all()
    })


@login_required
def delete_meeting_time(request, pk):
    if request.method == 'POST':
        MeetingTime.objects.filter(pk=pk).delete()
        return redirect('editmeetingtime')



# DEPARTMENT CRUD

@login_required
def addDepts(request):
    form = DepartmentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('addDepts')
    return render(request, 'addDepts.html', {'form': form})


@login_required
def department_list(request):
    return render(request, 'deptlist.html', {
        'departments': Department.objects.all()
    })


@login_required
def delete_department(request, pk):
    if request.method == 'POST':
        Department.objects.filter(pk=pk).delete()
        return redirect('editdepartment')


# SECTION CRUD

@login_required
def addSections(request):
    form = SectionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('addSections')
    return render(request, 'addSections.html', {'form': form})


@login_required
def section_list(request):
    return render(request, 'seclist.html', {
        'sections': Section.objects.all()
    })


@login_required
def delete_section(request, pk):
    if request.method == 'POST':
        Section.objects.filter(pk=pk).delete()
        return redirect('editsection')



# SIMPLE GENERATE PAGE
@login_required
def generate(request):
    return render(request, 'generate.html')


# PDF EXPORT VIEW
class Pdf(View):
    def get(self, request):
        return Render.render('gentimetable.html', {'request': request})
