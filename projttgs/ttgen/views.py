from django.shortcuts import render, redirect
from .forms import *
from .models import *
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.generic import View
import random as rnd

# GA PARAMETERS
# GA PARAMETERS
POPULATION_SIZE = 9
NUMB_OF_ELITE_SCHEDULES = 1
TOURNAMENT_SELECTION_SIZE = 3
MUTATION_RATE = 0.05

LAB_DURATION = 4

# Lab blocks: Morning (1–4) OR Afternoon (6–9)
VALID_LAB_START_SLOTS = ["1", "6"]

# Lunch slot (no class/lab here)
LUNCH_SLOT = "5"


# ---------------- DATA WRAPPER ----------------

class Data:
    def __init__(self):
        self._rooms = list(Room.objects.all())
        self._meetingTimes = list(MeetingTime.objects.all())
        self._instructors = list(Instructor.objects.all())
        self._courses = list(Course.objects.all())
        self._depts = list(Department.objects.all())

    def get_rooms(self): return self._rooms
    def get_instructors(self): return self._instructors
    def get_courses(self): return self._courses
    def get_depts(self): return self._depts
    def get_meetingTimes(self): return self._meetingTimes

    def get_lab_rooms(self):
        return [r for r in self._rooms if r.room_type == "Lab"]

    def get_lecture_rooms(self):
        return [r for r in self._rooms if r.room_type != "Lab"]


data = None


# ---------------- CLASS & LAB OBJECTS ----------------

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
    def set_meetingTime(self, mt): self.meeting_time = mt
    def set_room(self, room): self.room = room


class Lab:
    def __init__(self, id, dept, section, course):
        self.section_id = id
        self.department = dept
        self.course = course
        self.instructor = None
        self.room = None
        self.section = section
        self.duration = LAB_DURATION
        self.meeting_times = []

    def set_instructor(self, instructor): self.instructor = instructor
    def set_meetingTimes(self, mts): self.meeting_times = mts
    def set_room(self, room): self.room = room


# ---------------- SCHEDULE ----------------

class Schedule:
    def __init__(self):
        self._data = data
        self._labs = []
        self._classes = []
        self._fitness = -1
        self._isFitnessChanged = True
        self._numberOfConflicts = 0
        self._labNumb = 0
        self._classNumb = 0

    def get_labs(self): return self._labs
    def get_classes(self): return self._classes

    def get_fitness(self):
        if self._isFitnessChanged:
            self._fitness = self.calculate_fitness()
            self._isFitnessChanged = False
        return self._fitness

    # ------ get 4 consecutive slots for lab (1–4 or 6–9) ------
    def _get_consecutive_slots(self, day, start_slot):
        all_times = self._data.get_meetingTimes()
        order = ["1","2","3","4","5","6","7","8","9"]

        day_slots = [mt for mt in all_times if mt.day == day]
        day_slots.sort(key=lambda mt: order.index(mt.time))

        try:
            idx = next(i for i, mt in enumerate(day_slots) if mt.time == start_slot)
        except StopIteration:
            return []

        end = idx + LAB_DURATION - 1
        if end >= len(day_slots):
            return []

        block = day_slots[idx:end+1]

        # if any slot is lunch → invalid block
        for mt in block:
            if mt.time == LUNCH_SLOT:
                return []

        return block

    # ------ conflict checks --------
    def _conflicts_if_assign_lab(self, mts, room, instructor, section):
        # Against labs
        for lab in self._labs:
            for mt in mts:
                if mt in lab.meeting_times:
                    if lab.section == section: return True
                    if lab.room == room: return True
                    if lab.instructor == instructor: return True

        # Against classes
        for cls in self._classes:
            for mt in mts:
                if (cls.meeting_time and
                    cls.meeting_time.day == mt.day and
                    cls.meeting_time.time == mt.time):
                    if cls.section == section: return True
                    if cls.room == room: return True
                    if cls.instructor == instructor: return True

        return False

    def _conflicts_if_assign_class(self, mt, room, instructor, section):
        # VS labs
        for lab in self._labs:
            if mt in lab.meeting_times:
                if lab.section == section: return True
                if lab.room == room: return True
                if lab.instructor == instructor: return True

        # VS other classes
        for cls in self._classes:
            if (cls.meeting_time and
                cls.meeting_time.day == mt.day and
                cls.meeting_time.time == mt.time):
                if cls.section == section: return True
                if cls.room == room: return True
                if cls.instructor == instructor: return True

        return False

    # ------ initialize labs first ------
    def initialize_labs(self):
        sections = Section.objects.all()
        lab_rooms = self._data.get_lab_rooms()
        all_mt = self._data.get_meetingTimes()
        days = sorted(list(set(mt.day for mt in all_mt)))

        for section in sections:
            dept = section.department
            lab_courses = [c for c in dept.courses.all() if c.room_required == "Lab"]

            for course in lab_courses:
                insts = list(course.instructors.all())
                if not insts:
                    continue

                newLab = Lab(self._labNumb, dept, section.section_id, course)
                self._labNumb += 1

                assigned = False
                attempts = 0

                while not assigned and attempts < 50:
                    attempts += 1
                    day = rnd.choice(days)
                    start_slot = rnd.choice(VALID_LAB_START_SLOTS)  # "1" or "6"

                    block = self._get_consecutive_slots(day, start_slot)
                    if not block:
                        continue

                    room = rnd.choice(lab_rooms)
                    instructor = rnd.choice(insts)

                    if not self._conflicts_if_assign_lab(block, room, instructor, section.section_id):
                        newLab.set_meetingTimes(block)
                        newLab.set_room(room)
                        newLab.set_instructor(instructor)
                        assigned = True

                if assigned:
                    self._labs.append(newLab)

        return self

    # ------ initialize regular classes (no lunch) ------
    def initialize_classes(self):
        sections = Section.objects.all()
        # Do NOT use slot 5 (lunch) for classes
        all_mt = [mt for mt in self._data.get_meetingTimes() if mt.time != LUNCH_SLOT]
        class_rooms = self._data.get_lecture_rooms()

        for section in sections:
            dept = section.department
            reg_courses = [c for c in dept.courses.all() if c.room_required != "Lab"]
            if not reg_courses:
                continue

            total = section.num_class_in_week
            idx = 0

            for _ in range(total):
                course = reg_courses[idx % len(reg_courses)]
                idx += 1
                insts = list(course.instructors.all())
                if not insts:
                    continue

                newClass = Class(self._classNumb, dept, section.section_id, course)
                self._classNumb += 1

                assigned = False
                attempts = 0
                while not assigned and attempts < 50:
                    attempts += 1
                    mt = rnd.choice(all_mt)
                    room = rnd.choice(class_rooms)
                    instructor = rnd.choice(insts)

                    if not self._conflicts_if_assign_class(mt, room, instructor, section.section_id):
                        newClass.set_meetingTime(mt)
                        newClass.set_room(room)
                        newClass.set_instructor(instructor)
                        assigned = True

                if assigned:
                    self._classes.append(newClass)

        return self

    def initialize(self):
        self.initialize_labs()
        self.initialize_classes()
        return self

    # ------ fitness: count conflicts ------
    def calculate_fitness(self):
        conflicts = 0

        # class ↔ class
        for i, c1 in enumerate(self._classes):
            for c2 in self._classes[i+1:]:
                if c1.meeting_time and c2.meeting_time:
                    same = (c1.meeting_time.day == c2.meeting_time.day and
                            c1.meeting_time.time == c2.meeting_time.time)
                    if same:
                        if c1.section == c2.section: conflicts += 1
                        if c1.room == c2.room: conflicts += 1
                        if c1.instructor == c2.instructor: conflicts += 1

        # lab ↔ lab
        for i, l1 in enumerate(self._labs):
            for l2 in self._labs[i+1:]:
                for mt in l1.meeting_times:
                    if mt in l2.meeting_times:
                        if l1.section == l2.section: conflicts += 1
                        if l1.room == l2.room: conflicts += 1
                        if l1.instructor == l2.instructor: conflicts += 1

        # lab ↔ class
        for lab in self._labs:
            for cls in self._classes:
                if cls.meeting_time in lab.meeting_times:
                    if cls.section == lab.section: conflicts += 1
                    if cls.room == lab.room: conflicts += 1
                    if cls.instructor == lab.instructor: conflicts += 1

        self._numberOfConflicts = conflicts
        return 1 / (1 + conflicts)


# ---------------- GA ----------------

class Population:
    def __init__(self, size):
        self._schedules = [Schedule().initialize() for _ in range(size)]

    def get_schedules(self):
        return self._schedules


class GeneticAlgorithm:
    def evolve(self, pop):
        return self._mutate_population(self._crossover_population(pop))

    def _crossover_population(self, pop):
        cp = Population(0)
        cp.get_schedules().append(pop.get_schedules()[0])  # elite

        while len(cp.get_schedules()) < POPULATION_SIZE:
            s1 = self._tournament(pop)
            s2 = self._tournament(pop)
            cp.get_schedules().append(self._crossover(s1, s2))

        return cp

    def _mutate_population(self, pop):
        for i in range(1, POPULATION_SIZE):
            if rnd.random() < MUTATION_RATE:
                pop.get_schedules()[i] = Schedule().initialize()
        return pop

    def _crossover(self, s1, s2):
        child = Schedule().initialize()

        labs_min = min(len(child.get_labs()), len(s1.get_labs()), len(s2.get_labs()))
        for i in range(labs_min):
            child.get_labs()[i] = s1.get_labs()[i] if rnd.random() > 0.5 else s2.get_labs()[i]

        cls_min = min(len(child.get_classes()), len(s1.get_classes()), len(s2.get_classes()))
        for i in range(cls_min):
            child.get_classes()[i] = s1.get_classes()[i] if rnd.random() > 0.5 else s2.get_classes()[i]

        return child

    def _tournament(self, pop):
        tpop = Population(0)
        for _ in range(TOURNAMENT_SELECTION_SIZE):
            tpop.get_schedules().append(pop.get_schedules()[rnd.randrange(POPULATION_SIZE)])
        tpop.get_schedules().sort(key=lambda s: s.get_fitness(), reverse=True)
        return tpop.get_schedules()[0]


# ---------------- TIMETABLE VIEW ----------------

def timetable(request):
    global data
    data = Data()

    # --- Run GA to get best schedule ---
    population = Population(POPULATION_SIZE)
    ga = GeneticAlgorithm()

    MAX_GEN = 200
    FITNESS_THRESHOLD = 0.90

    population.get_schedules().sort(key=lambda s: s.get_fitness(), reverse=True)
    gen = 0

    while True:
        best = population.get_schedules()[0].get_fitness()
        print(f"Generation {gen:03d} | Best fitness = {best:.4f}")

        if best >= FITNESS_THRESHOLD or gen >= MAX_GEN:
            break

        population = ga.evolve(population)
        population.get_schedules().sort(key=lambda s: s.get_fitness(), reverse=True)
        gen += 1

    best_schedule = population.get_schedules()[0]

    # ---- Time / days ----
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    SLOT_LABELS = {
        "1": "8:30 - 9:30",
        "2": "9:30 - 10:30",
        "3": "10:30 - 11:30",
        "4": "11:30 - 12:30",
        "5": "12:30 - 1:30",   # Lunch
        "6": "1:30 - 2:30",
        "7": "2:30 - 3:30",
        "8": "3:30 - 4:30",
        "9": "4:30 - 5:30",
    }

    sections = list(Section.objects.all())
    all_labs = best_schedule.get_labs()
    all_classes = best_schedule.get_classes()

    # ---------------------------
    # Build a ready-to-render grid
    # ---------------------------
    # tables = [ { "section": <Section>, "rows": [ { "day": "Monday", "cells": [ {...}, ... ] }, ... ] } ]
    tables = []

    for section in sections:
        section_rows = []

        for day in days:
            cells = []
            slot = 1
            while slot <= 9:
                # Slot 5 = lunch
                if slot == 5:
                    cells.append({
                        "type": "lunch",
                        "colspan": 1,
                        "lab": None,
                        "classes": [],
                    })
                    slot += 1
                    continue

                # Check if a LAB starts here (strict: only slot 1 or 6 allowed, GA already enforces)
                lab_here = None
                for lab in all_labs:
                    if (
                        lab.section == section.section_id and
                        lab.meeting_times and
                        lab.meeting_times[0].day == day and
                        int(lab.meeting_times[0].time) == slot
                    ):
                        lab_here = lab
                        break

                if lab_here is not None:
                    # One big 4-slot rectangle: colspan=4
                    cells.append({
                        "type": "lab",
                        "colspan": 4,
                        "lab": lab_here,
                        "classes": [],
                    })
                    slot += 4
                    continue

                # No lab starting here → check for classes at this slot
                classes_here = [
                    cls for cls in all_classes
                    if (
                        cls.section == section.section_id and
                        cls.meeting_time is not None and
                        cls.meeting_time.day == day and
                        int(cls.meeting_time.time) == slot
                    )
                ]

                if classes_here:
                    cells.append({
                        "type": "class",
                        "colspan": 1,
                        "lab": None,
                        "classes": classes_here,
                    })
                else:
                    cells.append({
                        "type": "empty",
                        "colspan": 1,
                        "lab": None,
                        "classes": [],
                    })

                slot += 1

            section_rows.append({
                "day": day,
                "cells": cells,
            })

        tables.append({
            "section": section,
            "rows": section_rows,
        })

    return render(request, "gentimetable.html", {
        "tables": tables,
        "SLOT_LABELS": SLOT_LABELS,
    })





# BASIC NAVIGATION VIEWS
def index(request): return render(request, 'index.html')
def about(request): return render(request, 'aboutus.html')
def help(request): return render(request, 'help.html')
def terms(request): return render(request, 'terms.html')


# CONTACT FORM
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


# CRUD VIEWS
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


@login_required
def generate(request):
    return render(request, 'generate.html')


class Pdf(View):
    def get(self, request):
        return Render.render('gentimetable.html', {'request': request})
