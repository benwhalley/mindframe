---
author: Kim et al
source: https://arxiv.org/pdf/2406.08718
---


Description Prompt

```
The following is a transcript of a chat between a psy- chotherapist and a client about {client’s mental disor- der}.
```


Condition prompt

```
The client starts the conversation as [client] and the psychotherapist starts the conversation as [psychotherapist]. Please use the dialog and speakers info as a guide to continue your consultation like #format#. Never create anything other than the #format# and just complete the “utterance” part.

#format#
[client]: “utterance” 
[psychotherapist]: “utterance”
```










Zero shot prompt (figure 2)

```
The following is a transcript of a chat between a psy- chotherapist and a client about depression. The client starts the conversation as [client] and the psychother- apist starts the conversation as [psychotherapist]. Please complete new transcript about [Question].
[Question]
[client] I’m almost never happy. Half of the time, I don’t feel anything. I find it easy to make myself feel nothing. I know I push people away because it’s easier. I just want answers. I’m sick of feeling this way. It’s ruining my relationships with people. [psychotherapist]
```








Figure 3: Few shot prompt example:

```
The following is a transcript of a chat between a psychotherapist and a client about depression. The client starts the conversation as [client] and the psychotherapist starts the conversation as [psy- chotherapist]. Please use the following [Example] as a guide complete new transcript about [Question].
[Example]
[client] They don’t go away, and I feel like I’m going crazy. Does that ever stop? Can it be a symptom of medication?
[psychotherapist] Since you realize that hearing voices in your head is not usual for you, then def- initely there is a problematic situation happening within your awareness of who you are.if you recently started taking a new drug or increased dosage of one you already were taking, and the voices started shortly after, then yes, it is possible medication created your problem.Start by telling whoever gave you the presecription, about the problem you ́re having.”Crazy” has some flexibility as to whether someone is this way or not.Certainly a very positive sign that you ́re not crazy, is that you ́re self-aware of a problem within yourself. And, you ́re responsible toward yourself and making effort to address this problem.Crazy people usually don ́t do responsible behaviors.
[client] I’ve been taking the same medication for a while now, but the dosage was increased a few weeks ago. Could that be the cause of the voices? [psychotherapist] That’s a good point. The dosage increase could definitely be a contributing factor. It’s possible that your body is reacting to the higher dosage in a way that’s causing these symptoms. I would still recommend reporting this to your prescribing doctor, as they can help you determine the best course of action.

[Question]
[client] I have been dealing with depression and anxiety for a number of years. I have been on medication, but lately my depression has felt worse. Can counseling help?
[psychotherapist]
```




Judgement prompt

```
You’re an assistant who evaluates answers strictly from the psychotherapist’s perspective about {mental disorder category}. Please rate [Answer 1] and [Answer 2] for the consultation [Question], respectively. Rate the two answers on a scale of 1-5, with higher values indicating better answers.
```
