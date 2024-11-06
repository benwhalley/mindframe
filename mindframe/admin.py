# admin.py

from django.contrib import admin
from .models import (
    CustomUser,
    Intervention,
    Cycle,
    TreatmentSession,
    Step,
    Transition,
    Turn,
    Note,
    Example,    
    TreatmentSessionState,
    Judgement,
    JudgementReturnType
)

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'email')

class ExampleInline(admin.TabularInline):
    model = Example
    extra = 1

@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ('title',) # 'version')
    search_fields = ('title',)
    inlines = [ExampleInline]

@admin.register(Cycle)
class CycleAdmin(admin.ModelAdmin):
    autocomplete_fields=['intervention', 'client']
    list_display = ( 'start_date',  'client', 'intervention', 'end_date')
    list_filter = ('start_date', 'end_date')
    search_fields = ('client__username', 'intervention__name')

@admin.register(TreatmentSession)
class TreatmentSessionAdmin(admin.ModelAdmin):
    autocomplete_fields=['cycle']
    list_display = ('id', 'cycle', 'started', 'last_updated')
    list_filter = ('started', 'last_updated')
    search_fields = ('cycle__client__username',)

class TransitionInline(admin.TabularInline):
    model = Transition
    fk_name = 'from_step'  # Indicates that `from_step` in Transition is the foreign key to Step
    extra = 1  # Number of extra blank transitions to display in admin
    autocomplete_fields = ('to_step','judgements')


@admin.register(Step)
class StepAdmin(admin.ModelAdmin):
    list_display = ('title', 'intervention')
    autocomplete_fields = ('intervention',)
    search_fields = ('title', 'intervention__title')
    inlines = [TransitionInline]

@admin.register(Transition)
class TransitionAdmin(admin.ModelAdmin):
    list_display = ('from_step', 'to_step')
    search_fields = ('from_step__name', 'to_step__name')

@admin.register(Turn)
class TurnAdmin(admin.ModelAdmin):
    list_display = ('speaker', 'session__id',"text", 'timestamp')
    list_filter = ('speaker', 'timestamp')
    search_fields = ('session__cycle__client__username',)

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('session__id', 'judgement', 'val', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('session__cycle__client__username',)
    autocomplete_fields=['session', ]

@admin.register(JudgementReturnType)
class JudgementReturnTypeAdmin(admin.ModelAdmin):
    list_display=['title', 'schema']



@admin.register(Judgement)
class JudgementAdmin(admin.ModelAdmin):
    autocomplete_fields=['intervention', ]
    search_fields=['title', 'intervention__title']



@admin.register(Example)
class ExampleAdmin(admin.ModelAdmin):
    list_display = ('intervention', 'title')
    list_filter = ('intervention',)
    search_fields = ('title', 'intervention__title',)




@admin.register(TreatmentSessionState)
class TreatmentSessionStateAdmin(admin.ModelAdmin):
    pass

