from django.contrib import admin
from .models import Course, Resource, ReportIssue


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
    'course_code',
    'course_title',
    'hard_prerequisite',
    'soft_prerequisite',
    'lab_type',
    'resource_count',
)

    search_fields = (
    'course_code',
    'course_title',
    'hard_prerequisite',
    'soft_prerequisite',
)

    list_filter = (
        'lab_type',
    )

    ordering = ('course_code',)

    fieldsets = (
        ('Course Information', {
            'fields': (
    'course_code',
    'course_title',
    'description',
    'hard_prerequisite',
    'soft_prerequisite',
    'lab_type',
)
        }),
    )

    def resource_count(self, obj):
        return obj.resources.count()

    resource_count.short_description = 'Resources'


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'course',
        'category',
        'exam_part',
        'question_type',
        'semester',
        'has_solution',
        'has_file',
        'has_link',
        'uploaded_at',
        'updated_at',
    )

    list_filter = (
        'course',
        'category',
        'exam_part',
        'question_type',
        'semester',
    )

    search_fields = (
        'title',
        'course__course_code',
        'course__course_title',
        'description',
        'semester',
    )

    ordering = ('course__course_code', 'exam_part', 'category', '-uploaded_at')
    list_per_page = 25
    readonly_fields = ('uploaded_at', 'updated_at', 'admin_help_text')

    fieldsets = (
        ('1. Basic Resource Information', {
            'fields': (
                'course',
                'title',
                'category',
                'exam_part',
                'semester',
            )
        }),

        ('2. Question Settings', {
            'fields': (
                'question_type',
                'admin_help_text',
            ),
            'description': 'Only use this section if Category is set to Questions.'
        }),

        ('Main Resource', {
    'fields': (
        'file',
        'external_link',
    )
}),

('Solution / Answer', {
    'fields': (
        'solution_file',
        'solution_link',
    ),
    'description': 'Optional. Only use this for question resources if a solution/answer is available.'
}),

        ('4. Optional Description', {
            'fields': (
                'description',
                'uploaded_at',
                'updated_at',
            )
        }),
    )

    def admin_help_text(self, obj):
        return (
            "Use Question Type only when Category = Questions. "
            "For slides, notes, videos, books, lab files, and links, leave it empty."
        )

    admin_help_text.short_description = 'Important Note'

    def has_file(self, obj):
        return bool(obj.file)

    has_file.boolean = True
    has_file.short_description = 'File?'

    def has_link(self, obj):
        return bool(obj.external_link)

    has_link.boolean = True
    has_link.short_description = 'Link?'

    def has_solution(self, obj):
        return bool(obj.solution_file or obj.solution_link)

    has_solution.boolean = True
    has_solution.short_description = 'Solution'

@admin.register(ReportIssue)
class ReportIssueAdmin(admin.ModelAdmin):
    list_display = (
        'issue_type',
        'course_code',
        'status',
        'submitted_at',
        'contact_email',
    )

    list_filter = (
        'issue_type',
        'status',
        'submitted_at',
    )

    search_fields = (
        'course_code',
        'resource_title_or_link',
        'details',
        'contact_email',
    )

    readonly_fields = (
        'issue_type',
        'course_code',
        'resource_title_or_link',
        'details',
        'contact_email',
        'submitted_at',
    )

    ordering = ('-submitted_at',)

    fieldsets = (
        ('Report Information', {
            'fields': (
                'issue_type',
                'course_code',
                'resource_title_or_link',
                'details',
                'contact_email',
                'submitted_at',
            )
        }),
        ('Admin Action', {
            'fields': (
                'status',
            )
        }),
    )