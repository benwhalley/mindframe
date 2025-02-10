class TreatmentSession(models.Model):

    def get_judgements_to_run(self, step, judgements):
        # find all the judgements that should be run on every turn
        potential_judgements_to_run = Judgement.objects.filter(
            pk__in=(judgements.values_list("judgement", flat=True))
        ).annotate(
            notes_count=Count(
                "notes",
                filter=Q(notes__turn__session_state__session__cycle=self.cycle)
                & ~Q(notes__data__value=None),
            )
        )

        # exclude ones where we already have a note and we only want to run once
        judgements_to_run = potential_judgements_to_run.exclude(
            stepjudgements__once=True, notes_count__gt=0
        )
        # log which ones we skipped
        for i in potential_judgements_to_run.filter(stepjudgements__once=True, notes_count__gt=0):
            nts = Note.objects.filter(
                judgement=i, turn__session_state__session__cycle=self.cycle
            ).values("data")
            logger.debug(f"SKIPPED JUDGEMENT: {i} - Existing Notes: {nts}")

        return judgements_to_run

    def build_client_data_dict(self, step):
        """Make a dictionary of the MOST RECENT note for each judgement variable plus metadata"""
        session_notes = Note.objects.filter(turn__session_state__session=self).filter(
            data__isnull=False
        )
        client_data = defaultdict(lambda: None)
        client_data.update(
            dict(
                session_notes.order_by("judgement__variable_name", "-timestamp").distinct(
                    "judgement__variable_name"
                )
                # `data`` can contain multiple values, each defined by a different completion - see return_type_models.py
                .values_list("judgement__variable_name", "data")
            )
        )

        # add metadata to this dict to use as context in evaluating transition conditions
        client_data.update(
            {
                "n_turns_step": self.turns.filter(session_state__step=step).count(),
                "n_turns_session": self.turns.filter().count(),
            }
        )
        logger.debug(f"DATA DETERMINING TRANSITION: {client_data}")
        return client_data

    def evaluate_transitions_and_update_step(self, turn, step, transitions, client_data):
        # check each of the conditions for each transition, line by line
        # all of the conditions must hold for the transition to be made
        # conditions are evaluated in a clean context with no globals but
        # do have access to the client_data default dictionary (default=None)

        # TODO: helping users debug their conditions and providing sensible error
        # messages will be important here and needs to be added.

        # convert to a dotten namespace to allowed dotted access to vars in conditions users write
        # from box import Box
        # x=Box({'a': {'c':3}, 'b': 2}, default_box=True)
        # eval("x.a.c", {}, x) == x.a.c
        # eval("a.a.c", {}, x) == x.a.c

        client_data = Box(client_data, default_box=True)
        logger.debug(f"CLIENT DATA AS BOX: {client_data}")
        transition_results = [
            (
                t,
                [
                    (c, eval(c, {}, client_data))
                    for c in list(map(str.strip, filter(bool, t.conditions.split("\n"))))
                ],
            )
            for t in transitions
        ]

        transition_results = [(i, all([r for c, r in l]), l) for i, l in transition_results]
        logger.debug(f"TRANSITION RESULTS: {transition_results}")

        # Find transitions that passed (if any)
        next_step = None
        valid_transitions = [t for t, passed, l in transition_results if passed]
        if valid_transitions:
            # for now, just pick the first transition that passed
            next_step = transitions[0].to_step
            newstate = TreatmentSessionState.objects.create(
                session=self, previous_step=step, step=next_step
            )
            newstate.save()

            # do any extra judgements needed
            step_jgm_enter_exit = StepJudgement.objects.filter(
                Q(
                    pk__in=next_step.stepjudgements.filter(
                        when=StepJudgementFrequencyChoices.ENTER
                    ).values("pk")
                )
                | Q(
                    pk__in=step.stepjudgements.filter(
                        when=StepJudgementFrequencyChoices.EXIT
                    ).values("pk")
                )
            )

            judgements_to_run = self.get_judgements_to_run(step, step_jgm_enter_exit)
            logger.debug(f"ENTRY/EXIT JUDGEMENTS TO RUN: {judgements_to_run}")

            # then do the judgements we need
            jvals_ = [j.make_judgement(turn) for j in judgements_to_run]

            step = next_step  # Update the step to reflect the new state

        return step

    @observe(capture_input=False, capture_output=False)
    def respond(self):
        """Respond to the client's last utterance (and manage transitions)."""
        logger.info("Starting response")

        bot = CustomUser.objects.filter(role=RoleChoices.THERAPIST).first()
        if not bot:
            raise Exception("No therapist user found to respond to client.")

        step = self.current_step()
        transitions = step.transitions_from.all()
        logger.info(f"Step: {step}, Transitions: {transitions}")

        # for now, just get all the judgements that are run on every turn
        turn_jgmnts = step.stepjudgements.filter(when=StepJudgementFrequencyChoices.TURN)
        judgements_to_run = self.get_judgements_to_run(step, turn_jgmnts)
        logger.info(f"TURN JUDGEMENTS TO RUN: {judgements_to_run}")

        # generate a new turn for the bot
        newturn = Turn.objects.create(
            speaker=bot, session_state=self.state, source_type=TurnSourceTypes.AI
        )
        newturn.save()

        logger.info(f"New turn created: {newturn}")

        # do the judgements we need now
        [j.make_judgement(newturn) for j in judgements_to_run]

        client_data = self.build_client_data_dict(step)

        step = self.evaluate_transitions_and_update_step(newturn, step, transitions, client_data)

        completions = step.spoken_response(newturn)

        utterance = completions.response
        # save the generated response and other data to the new Turn
        newturn.session_state = self.state  # update in case we changed step
        newturn.text = utterance
        newturn.metadata = dict(completions.items())
        newturn.save()

        thoughts = "TODO: ENSURE A SUMMARY OF MODEL THINKING IS MADE HERE?"

        langfuse_context.update_current_observation(
            name=f"Response: {self.state} ({self.cycle.intervention})",
            session_id=self.uuid,
            output=utterance,
        )
        langfuse_context.flush()

        return {"utterance": utterance, "thoughts": thoughts}


class Step(models.Model):
    """Represents a step in an intervention, including a prompt template and Judgements."""

    def natural_key(self):
        return slugify(f"{self.intervention.title}__{self.title}")

    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE, related_name="steps")

    title = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(default=1)
    slug = AutoSlugField(populate_from="title")
    prompt_template = models.TextField()
    judgements = models.ManyToManyField("Judgement", through="StepJudgement")

    def get_absolute_url(self):
        return reverse("admin:mindframe_step_change", args=[str(self.id)])

    def make_data_variable(self, session):
        """This makes the `data` context variable, used in the prompt template.

        The layout/structure of this object is important because end-users will access it in templates and it needs to be consistent/predictable and provide good defaults.
        """

        def getv(notes, v):
            notes = notes.filter(judgement__variable_name=v)
            r = {v: notes.last().data, v + "__all": notes}
            return r

        # get all notes for this session and flatten them so that we can access the latest
        # instance of each Judgement/Note by variable name
        notes = Note.objects.filter(turn__session_state__session__cycle=session.cycle)
        vars = set(notes.values_list("judgement__variable_name", flat=True))
        dd = {}
        for i in vars:
            dd.update(getv(notes, i))

        return dd

    def get_step_context(self, session) -> dict:

        all_notes = Note.objects.filter(turn__session_state__session__cycle=session.cycle)
        all_turns = Turn.objects.filter(session_state__session__cycle=session.cycle)

        # ALI - THIS IS AN IMPORTANT PART BECAUSE IT PROVIDES CONTEXT FOR THE LLM WHEN RESPONDING TO CLIENTS AND ALSO WHEN MAKING JUDGEMENTS
        # FOR SOME THINGS WE WILL BE ABLE TO EXTEND THIS FUNCTION AND PROVIDE MORE CONTEXT
        # IN OTHER CASES (E.G. FOR RAG) WE WILL NEED TO MAKE A TEMPLATETAG AND USE THAT IN THE PROMPT TEMPLATE TO DYNAMICALLY EXTRACT EXTRA CONTEXT

        context = {
            "session": session,
            "intervention": session.cycle.intervention,
            "notes": all_notes.filter(turn__session_state__session=session).filter(
                timestamp__gt=session.state.timestamp
            ),
            "session_notes": all_notes.filter(turn__session_state__session=session),
            "all_notes": all_notes,
            "data": self.make_data_variable(session),
        }
        return context

    def get_model(self, session):
        # TODO FIX DEFAULTING
        m = session.cycle.intervention.default_conversation_model
        if m:
            return m
        return LLM.objects.filter(model_name="gpt-4o").first()

    @observe(capture_input=False, capture_output=False)
    def spoken_response(self, turn) -> OrderedDict:
        """Use an llm to create a spoken response to clients, using session data as context."""

        session = turn.session_state.session
        ctx = self.get_step_context(session)

        completions = chatter(
            self.prompt_template,
            context=ctx,
            model=self.get_model(session),
            log_context={
                "step": self,
                "session": session,
                "prompt": self.prompt_template,
                "turn": turn,
                "context": ctx,
            },
        )
        return completions

    @observe(capture_input=False, capture_output=False)
    def respond_in_conversation(self, respond_to, as_speaker):

        transcript = list(reversed(iter_conversation_path(respond_to, direction="up")))
        speaker_last_turn = respond_to.conversation.previous_turn_of_speaker(as_speaker)

        step = speaker_last_turn.step

        transitions = step.transitions_from.all()
        logger.info(f"Last used step: {step}.\nPossible transitions: {transitions}")

        # for now, just get all the judgements that are run on every turn
        turn_jgmnts = step.stepjudgements.filter(when=StepJudgementFrequencyChoices.TURN)
        judgements_to_run = self.get_judgements_to_run(step, turn_jgmnts)
        logger.info(f"TURN JUDGEMENTS TO RUN: {judgements_to_run}")

        # generate a new turn for the bot
        newturn = Turn.objects.create(
            speaker=bot, session_state=self.state, source_type=TurnSourceTypes.AI
        )
        newturn.save()

        logger.info(f"New turn created: {newturn}")

        # do the judgements we need now
        [j.make_judgement(newturn) for j in judgements_to_run]

        client_data = self.build_client_data_dict(step)

        step = self.evaluate_transitions_and_update_step(newturn, step, transitions, client_data)

        completions = step.spoken_response(newturn)

        utterance = completions.response
        # save the generated response and other data to the new Turn
        newturn.session_state = self.state  # update in case we changed step
        newturn.text = utterance
        newturn.metadata = dict(completions.items())
        newturn.save()

        thoughts = "TODO: ENSURE A SUMMARY OF MODEL THINKING IS MADE HERE?"

        langfuse_context.update_current_observation(
            name=f"Response: {self.state} ({self.cycle.intervention})",
            session_id=self.uuid,
            output=utterance,
        )
        langfuse_context.flush()

        return {"utterance": utterance, "thoughts": thoughts}

    class Meta:
        unique_together = [("intervention", "title"), ("intervention", "slug")]
        ordering = ["intervention", "order", "title"]

    def __str__(self):
        return f"{self.title} ({self.intervention.title}, {self.intervention.sem_ver}/{self.intervention.ver()})"


class Judgement(models.Model):
    """A Judgement to be made on the current Conversation state.

        Judgements are defined by a prompt template and expected return type/acceptable return values.

    jj =Judgement.objects.last()
    ss = TreatmentSession.objects.last()
    tt = ss.turns.all().last()
    jr = jj.make_judgement(tt)
    jr.items()
    """

    def natural_key(self):
        return slugify(f"{self.variable_name}")

    intervention = models.ForeignKey("mindframe.Intervention", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    slug = AutoSlugField(populate_from="title")
    variable_name = models.CharField(max_length=255)
    task_summary = models.TextField(
        blank=True,
        null=True,
        help_text="A brief summary of the task or question asked by this judgement. E.g. 'Evaluate the client's emotional state'.",
    )
    prompt_template = models.TextField()

    @observe(capture_input=False, capture_output=False)
    def make_judgement(self, turn):
        """

        s = TreatmentSession.objects.last()
        self = Judgement.objects.first()
        self.make_judgement(s)
        """

        session = turn.session_state.session
        logger.info(f"Making judgement {self.title} for {session}")
        try:
            result = self.process_inputs(
                turn, inputs=session.current_step().get_step_context(session)
            )
            langfuse_context.update_current_observation(
                name=f"Judgement: {self}",
                session_id=turn.session_state.session.uuid,
                # output = result.data
            )
            return result
        except Exception as e:
            logger.error(f"ERROR MAKING JUDGEMENT {e}")
            logger.error(traceback.print_exc())
            # TODO: find some way of making this error more obvious to users
            return None

    def get_model(self, session):
        return session.cycle.intervention.default_conversation_model

    def process_inputs(self, turn, inputs: dict):

        newnote = Note.objects.create(judgement=self, turn=turn, inputs=None)
        session = turn.session_state.session

        llm_result = chatter(
            self.prompt_template,
            model=self.get_model(session),
            context=inputs,
            log_context={"judgement": self, "session": session, "inputs": inputs, "turn": turn},
        )

        newnote.data = llm_result
        newnote.save()
        return newnote

    def __str__(self) -> str:
        return f"<{self.variable_name}> {self.title} ({self.intervention.title} {self.intervention.sem_ver})"

    class Meta:
        unique_together = [("intervention", "title"), ("intervention", "slug")]


class SyntheticConversation(models.Model):
    """A synthetic conversation between two TreatmentSessions"""

    session_one = models.ForeignKey(
        TreatmentSession, on_delete=models.CASCADE, related_name="conversation_one"
    )
    session_two = models.ForeignKey(
        TreatmentSession, on_delete=models.CASCADE, related_name="conversation_two"
    )
    start_time = models.DateTimeField(default=timezone.now)

    # because each TreatmentSession needs a full record of both speaker and listener (i.e. both sides of the conversation) we need to keep track of who spoke last manually for convenience
    last_speaker_turn = models.ForeignKey("Turn", on_delete=models.CASCADE, null=True, blank=True)

    additional_turns_scheduled = models.PositiveSmallIntegerField(
        default=0,
        help_text="Number of additional turns scheduled for this conversation (should be completed by a worker task — don't edit directly)",
    )

    def get_absolute_url(self):
        return reverse("synthetic_conversation_detail", args=[str(self.pk)])

    def __str__(self):
        return f"Synthetic conversation between Session {self.session_one.id} and Session {self.session_two.id} starting at {self.start_time}"
