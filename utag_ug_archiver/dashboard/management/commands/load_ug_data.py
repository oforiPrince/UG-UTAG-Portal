from django.core.management.base import BaseCommand
from accounts.models import School, College, Department

class Command(BaseCommand):
    help = 'Load University of Ghana schools, colleges, and departments'

    def handle(self, *args, **options):
        # Data for University of Ghana
        data = {
            'School of Arts': {
                'colleges': {
                    'College of Humanities': [
                        'Department of English',
                        'Department of History',
                        'Department of Philosophy and Classics',
                        'Department of Religions',
                        'Department of Theatre Arts',
                    ]
                }
            },
            'School of Sciences': {
                'colleges': {
                    'College of Basic and Applied Sciences': [
                        'Department of Biochemistry, Cell and Molecular Biology',
                        'Department of Botany',
                        'Department of Chemistry',
                        'Department of Computer Science',
                        'Department of Earth Science',
                        'Department of Mathematics',
                        'Department of Physics',
                        'Department of Statistics',
                    ]
                }
            },
            'School of Social Sciences': {
                'colleges': {
                    'College of Social Sciences': [
                        'Department of Economics',
                        'Department of Geography and Resource Development',
                        'Department of Political Science',
                        'Department of Psychology',
                        'Department of Sociology',
                    ]
                }
            },
            'School of Business': {
                'colleges': {
                    'College of Business': [
                        'Department of Accounting',
                        'Department of Finance',
                        'Department of Marketing and Entrepreneurship',
                        'Department of Operations Management and Information Systems',
                        'Department of Organisation and Human Resource Management',
                        'Department of Public Administration and Health Services Management',
                    ]
                }
            },
            'School of Law': {
                'colleges': {
                    'College of Law': [
                        'Department of Law',
                    ]
                }
            },
            'School of Engineering Sciences': {
                'colleges': {
                    'College of Basic and Applied Sciences': [
                        'Department of Agricultural Engineering',
                        'Department of Biomedical Engineering',
                        'Department of Computer Engineering',
                        'Department of Food Process Engineering',
                        'Department of Material Science and Engineering',
                        'Department of Petroleum Engineering',
                    ]
                }
            },
            'School of Agriculture': {
                'colleges': {
                    'College of Basic and Applied Sciences': [
                        'Department of Agricultural Economics and Agribusiness',
                        'Department of Agricultural Extension',
                        'Department of Animal Science',
                        'Department of Crop Science',
                        'Department of Soil Science',
                    ]
                }
            },
            'School of Biological Sciences': {
                'colleges': {
                    'College of Basic and Applied Sciences': [
                        'Department of Animal Biology and Conservation Science',
                        'Department of Biochemistry, Cell and Molecular Biology',
                        'Department of Botany',
                        'Department of Ecology and Environmental Biology',
                        'Department of Marine and Fisheries Sciences',
                        'Department of Microbiology',
                        'Department of Nutrition and Food Science',
                    ]
                }
            },
            'School of Physical and Mathematical Sciences': {
                'colleges': {
                    'College of Basic and Applied Sciences': [
                        'Department of Chemistry',
                        'Department of Computer Science',
                        'Department of Earth Science',
                        'Department of Mathematics',
                        'Department of Physics',
                        'Department of Statistics',
                    ]
                }
            },
            'School of Medicine and Health Sciences': {
                'colleges': {
                    'College of Health Sciences': [
                        'Department of Anaesthesia and Intensive Care',
                        'Department of Anatomy',
                        'Department of Behavioural Sciences',
                        'Department of Biochemistry',
                        'Department of Child Health',
                        'Department of Community Health',
                        'Department of Eye, Ear, Nose and Throat',
                        'Department of Family Medicine',
                        'Department of Haematology',
                        'Department of Internal Medicine',
                        'Department of Medical Biochemistry',
                        'Department of Medical Microbiology',
                        'Department of Obstetrics and Gynaecology',
                        'Department of Pathology',
                        'Department of Pharmacology',
                        'Department of Physiology',
                        'Department of Psychiatry',
                        'Department of Radiology',
                        'Department of Surgery',
                    ]
                }
            },
            'School of Pharmacy': {
                'colleges': {
                    'College of Health Sciences': [
                        'Department of Pharmaceutical Chemistry',
                        'Department of Pharmaceutics and Microbiology',
                        'Department of Pharmacognosy and Herbal Medicine',
                        'Department of Pharmacology',
                    ]
                }
            },
            'School of Nursing': {
                'colleges': {
                    'College of Health Sciences': [
                        'Department of Adult Health',
                        'Department of Community Health Nursing',
                        'Department of Maternal and Child Health',
                        'Department of Mental Health Nursing',
                        'Department of Nursing Administration and Education',
                    ]
                }
            },
            'School of Allied Health Sciences': {
                'colleges': {
                    'College of Health Sciences': [
                        'Department of Audiology, Speech and Language',
                        'Department of Dietetics',
                        'Department of Medical Laboratory Science',
                        'Department of Occupational Therapy',
                        'Department of Physiotherapy',
                        'Department of Radiography',
                        'Department of Sports and Exercise Science',
                    ]
                }
            },
            'School of Veterinary Medicine': {
                'colleges': {
                    'College of Basic and Applied Sciences': [
                        'Department of Animal Science',
                        'Department of Pathology',
                        'Department of Physiology',
                        'Department of Veterinary Clinical Studies',
                        'Department of Veterinary Pathology, Microbiology and Parasitology',
                    ]
                }
            },
        }

        for school_name, school_data in data.items():
            school, created = School.objects.get_or_create(name=school_name)
            if created:
                self.stdout.write(f'Created School: {school_name}')
            else:
                self.stdout.write(f'School already exists: {school_name}')

            for college_name, departments in school_data['colleges'].items():
                college, created = College.objects.get_or_create(name=college_name, school=school)
                if created:
                    self.stdout.write(f'  Created College: {college_name}')
                else:
                    self.stdout.write(f'  College already exists: {college_name}')

                for dept_name in departments:
                    dept, created = Department.objects.get_or_create(name=dept_name, college=college)
                    if created:
                        self.stdout.write(f'    Created Department: {dept_name}')
                    else:
                        self.stdout.write(f'    Department already exists: {dept_name}')

        self.stdout.write(self.style.SUCCESS('Successfully loaded UG schools, colleges, and departments'))