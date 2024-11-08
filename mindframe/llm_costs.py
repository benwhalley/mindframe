# Sum on input/output tokens
# sum(Turn.objects.filter(metadata__input_tokens__isnull=False).values_list('metadata__input_tokens', flat=True))
# sum(Turn.objects.filter(metadata__output_tokens__isnull=False).values_list('metadata__output_tokens', flat=True))
