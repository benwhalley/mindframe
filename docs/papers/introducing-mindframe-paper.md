






# The Promise of DeepSeek R1 for the Development of High-Quality Therapy AI

Recent advances in artificial intelligence have highlighted the necessity of moving beyond next-word prediction and toward systems that can dynamically engage in structured reasoning, a principle that underpins novel approaches such as DeepSeek R1.
By embedding self-improving mechanisms via reinforcement learning, these models can refine their decision-making processes without relying solely on pattern matching, and without the need for extremely-large naturalistic datasets or extended human supervision.

Psychotherapy poses unique hurdles to large-scale AI training. Confidentiality norms and strict data-sharing regulations hamper the collection of real-world therapy transcripts, limiting the volume of robust, ethically sourced training data [@Luxton2014]. Variability in therapeutic styles and the lack of explicit labels---critical for supervised learning---further complicate model development, raising questions about how to define "success" in a realm where outcomes hinge on subjective interpersonal dynamics [@Shatte2019]. Furthermore, inadequately curated datasets might lead to harm by inadvertently reproducing biases or outdated practices [@srinivasan2024comprehensive], an outcome antithetical to the principles of safe clinical care.

Models like DeepSeek R1 (Deepseek) suggest a way around these constraints, through the internal generation of structured reasoning sequences which are trained and refined with reinforcement signals that prioritise adherence to evidence-based frameworks [@Pereira2019]. Rather than replicating an -- often inconsistent -- archive of therapy sessions, this approach could foster explicit alignment with established clinical guidelines, offering an interpretable and scalable pathway to AI-assisted mental health interventions.  By bridging the gap between fluid language-generation and carefully orchestrated therapeutic reasoning, models adopting DeepSeek's approach represent a paradigm shift: from superficially imitating a corpus of imperfect therapeutic encounters, to internalising and applying core psychological principles responsibly and transparently.

Replicating DeepSeek’s approach for a therapist AI, requires a corpus of therapy sessions in which both the therapeutic reasoning _and_ interactions with clients are connected, and which contains annotations to incentivise models to reproduce both the therapuetic reasoning and client facing output (via RLHF/RLAIF).

We can separate this into two steps: first, generating a corpus of clinical-chains of thought (CCT), and second annotating that corpus with reward signals for later training.
There are two potential sources of such a corpus.

- Expert-generated chains of thought and responses to clients in response to real or realistic clinical scenarios.

- Prompting-only systems, which provide the necessary context and instructions for foundation models to produce CCT's and interact with clients (again, either in real or realistic clinical scenarios).

Although potentially feasible, using experts to generate extended chains of thought and client output to train foundation models has disadvantages of cost, time, and lack of variety and control. In contrast, prompting-only systems could be used to generate a large, diverse, and controlled dataset of CCT's and client output. Prompts could be varied systematically to optimise for desired characteristics, and the system could be used as part of an iterative process to refine the dataset and the model. These systems could also be used to deliver clinical services whilst models are developed, or be used to adapt/customise services to specific clinical contexts or individual client preferences.

Compared with AI-therapy implementations that prompt foundation models to simulate therapist speech and interact with clients, a system designed to generate COT would be slower and (marginally) more expensive, but also more introspectable and accountable, and substantially more informative for clinicians and researchers seeking to adapt and improve AI-based interventions. Another advantage of systems based on CCT-prompting is that they offer a clear path for collaboration between research groups and comparison of competing operationalisations of existing and novel therapeutic approaches.

Prerequisites for This Approach to Work

1. The instruction-only system must produce high-quality output. The dataset of collected interactions from the system must accurately reflect therapist reasoning and structured intervention principles.

2. Human evaluators or automated classifiers must be able to reliably assess the model's reasoning and responses. If used for reinforcement learning, these reward signals must effectively capture the qualitative aspects of good therapeutic thinking and responses.

In this paper we outline the steps necessary to produce a therapeutic equivalent of Deepseek R1, and report initial results from an open-source CCT-prompting system, [Mindframe](http://github.com/benwhalley/mindframe).



### A prompting-based system with hidden chain of thought reasoning

To generate the corpus of CCTs required to train a Deepseek-style therapist,
it is necessary to represent the structure and desired outputs of a therapeutic appraoch in a way that can be used to prompt a foundation model.
These prompts explicitly instruct the model to generate a _structured_ response, including an internal CoT reasoning component that remains hidden from the user.
This requires an explicit model of the therapeutic process intended — for example,, describing the goals and structure of a treatment session, or the broader principles of a specific therapeutic approach and the trajectory across a number of sessions.

Describing this broader structure in a single prompt is unlikely to be sucessful.
Studies on chain-of-thought prompting indicate that iterative, stepwise reasoning helps models maintain internal consistency and produce more accurate, context-sensitive outputs [@Wei2022chain]. By contrast, a single prompt encourages models to rely on static or memorised patterns, which would be incompatible with the complexity and personalised nature of mental health interventions [@Shatte2019].


>Brown et al. (2020). “Language Models are Few-Shot Learners.”
>[https://arxiv.org/abs/2005.14165]
>Although this paper introduces GPT-3’s few-shot capacities, the authors note that performance can decline on tasks requiring carefully maintained context over many turns. Their results suggest that extending prompts and chaining instructions can lead to errors or unfaithful completions.

> Wei et al. (2022). “Chain-of-Thought Prompting Elicits Reasoning in Large Language Models.”
>[https://arxiv.org/abs/2201.11903]
>While primarily focused on the benefits of chain-of-thought reasoning, the paper shows examples where LLMs lose coherence if the chain-of-thought extends too far. Longer chains or more steps can cause partial drift or confusion in subsequent reasoning.


>Liu et al. (2023). “Lost in the Middle: How Language Models Use Long Contexts.”
>[https://arxiv.org/abs/2307.03172]
>This paper examines how Transformer-based LLMs handle large context windows, showing that as prompt length increases, models sometimes neglect or “forget” relevant chunks of earlier context. This leads to both topic drift and inaccuracies when trying to follow detailed instructions across many turns.



This allows the model to follow established therapeutic paradigms, such as Motivational Interviewing (MI), Cognitive Behavioral Therapy (CBT), or Acceptance and Commitment Therapy (ACT), without overwhelming the client with unnecessary meta-commentary.


Each interaction follows a structured format:
1. **User Input**: The user submits a query, concern, or problem statement.
2. **Hidden Chain of Thought**: The model generates a structured internal reasoning sequence based on psychological principles.
3. **Final User-Facing Response**: A concise, empathetic response is presented to the user, ensuring clarity and accessibility.

By systematically collecting these interactions, we construct a dataset in which high-quality therapist responses are paired with explicit reasoning sequences. This dataset serves as the foundation for subsequent model refinement.


### Constructing a Training Dataset for Model Fine-Tuning
The dataset generated in the prompting stage contains three critical components: (1) user queries, (2) therapist CoT reasoning, and (3) final user-facing responses. Additionally, human evaluators or heuristic-based scoring mechanisms assess response quality. The resulting dataset enables fine-tuning a foundational large language model, embedding structured reasoning directly into its architecture rather than relying solely on prompting.

Supervised fine-tuning (SFT) on this dataset ensures that the model learns to generate its own CoT reasoning while preserving the clarity and structure of therapeutic interactions. The training objective is to align model-generated reasoning with expert therapist reasoning patterns, allowing the AI to internalize decision-making heuristics.

### Reinforcement Learning with AI Feedback (RLAIF) for Therapist Model Optimization
Fine-tuning alone is insufficient to ensure that the model produces high-quality therapeutic responses across diverse scenarios. To further refine the AI’s reasoning and response generation, we introduce a reinforcement learning stage that optimizes the model based on structured reward signals.

**Designing Reward Signals:**
1. **Adherence to Therapeutic Frameworks** – The model is rewarded for responses that follow structured psychological principles, such as the appropriate use of open-ended questions, affirmations, and reflections.
2. **Empathy and Emotional Appropriateness** – A secondary NLP classifier scores responses for warmth, compassion, and sensitivity.
3. **Logical Coherence in Chain of Thought Reasoning** – The model’s internal reasoning is evaluated for consistency and structured problem-solving.
4. **User Engagement and Outcome Metrics** – Where possible, longitudinal data is used to assess whether the AI-driven responses correlate with positive behavioral changes or continued user engagement.
5. **Human Preference Rankings** – Therapist evaluators rank multiple AI-generated responses, creating a dataset to train a reward model that optimizes for human-like therapeutic quality.

The optimization process employs **Group Relative Policy Optimization (GRPO)**, a reinforcement learning algorithm that improves model outputs by selecting responses that maximize alignment with predefined reward functions. Instead of direct reinforcement learning from human feedback (RLHF), GRPO enables the model to learn through a structured reward comparison process, iteratively refining its policy based on therapist-preferred responses.





### Evaluating quality

- Longitudinal user outcomes (weak signals, likely too noisy)
- Human evaluators (expensive, but probbly necessary in part)
- Automated scoring mechanisms


### Standing on the shoulders of giants

For this approach to work, it is important that the profession collaborates to produce a large, high-quality dataset.

We need this to be in our control — if abdicated to large tech companies, the data will be used for other purposes, and the quality of the data will be suboptimal for our purposes.

> https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2829839
> Large Language Models for Chatbot Health Advice Studies
A Systematic Review
> In this systematic review of 137 articles, 99.3% of the studies assessed closed-source models and did not provide enough information to identify the LLM. Most (64.5%) studies used subjective means as the ground truth to define the successful performance of the LLM, while less than a third addressed the ethical, regulatory, and patient safety implications of clinically integrating LLMs.


### Clinical collaboration


A recent large intergrative review on the application of mental health chatbots concluded that:
> creating pleasant and effective conversations with a mental health chatbot requires careful and professional planning in advance, defining the target group and working together with it to address its needs and preferences. It is essential to emphasise the pleasant user experience and safety from both technical and psychological perspectives.

[@nieminen2025recommendations]


Prompting-based approaches are critical to this, because they provide the flexiblity and introspectability necessary.


An earlier scoping review of mental health chatbots found that:
> To be useful for clinical practice, we have to find ways to harmonize chatbot content with individual treatment recommendations, that is, a personalization of chatbot conversations is required.

[@abd2021perceptions]


### Long term status of the scaffold

Mindframe essentially represents scaffolding, used to improve the foundation model.

However, it's not clear that the scaffold would ever be removed.

Benefits of retaining the scaffold in the longer term include:

- interpretability and accountability: by providing human supervisors with a clear summary of the model's reasoning, the scaffold ensures that the AI's decisions are transparent and can be audited

- adaptability - e.g. to create 'intersectional' therapeutic models which combine therapeutic approaches in novel ways

- control: e.g. for research we may want to


### Conclusion and Future Directions

This multi-stage approach—beginning with a structured prompting system, transitioning to supervised fine-tuning, and culminating in reinforcement learning—creates a robust pipeline for developing a high-quality therapist AI. The integration of hidden CoT reasoning ensures that the model systematically builds its responses based on psychological principles, while reinforcement learning optimizes for long-term user outcomes. Future work will explore live adaptation mechanisms that allow the AI to refine its reasoning dynamically through user interactions, as well as the potential for causal modeling to assess which intervention strategies yield the most effective results.





@article{Silver2017,
  title = {Mastering the game of Go without human knowledge},
  author = {Silver, David and Schrittwieser, Julian and Simonyan, Karen and others},
  journal = {Nature},
  volume = {550},
  number = {7676},
  pages = {354--359},
  year = {2017},
  publisher = {Nature Publishing Group}
}

@article{Levine2022,
  title = {Reinforcement Learning for Robotics and Control: Challenges and Opportunities},
  author = {Levine, Sergey},
  journal = {Annual Review of Control, Robotics, and Autonomous Systems},
  volume = {5},
  pages = {293--323},
  year = {2022}
}

@article{Fitzpatrick2017,
  title = {Delivering cognitive behavior therapy to young adults with symptoms of depression and anxiety using a fully automated conversational agent (Woebot): A pilot study},
  author = {Fitzpatrick, Kathleen K. and Darcy, Alison and Vierhile, Molly},
  journal = {JMIR Mental Health},
  volume = {4},
  number = {2},
  pages = {e19},
  year = {2017},
  publisher = {JMIR Publications}
}

@article{Luxton2014,
  title = {Recommendations for the ethical use and design of artificial intelligent care providers},
  author = {Luxton, David D.},
  journal = {Artificial Intelligence in Medicine},
  volume = {62},
  number = {1},
  pages = {1--10},
  year = {2014},
  publisher = {Elsevier}
}

@article{Shatte2019,
  title = {Machine learning in mental health: A scoping review of methods and applications},
  author = {Shatte, Adrian B. R. and Hutchinson, Dianne M. and Teague, Samantha J.},
  journal = {Psychological Medicine},
  volume = {49},
  number = {9},
  pages = {1426--1448},
  year = {2019},
  publisher = {Cambridge University Press}
}

@inproceedings{Buolamwini2018,
  title = {Gender Shades: Intersectional Accuracy Disparities in Commercial Gender Classification},
  author = {Buolamwini, Joy and Gebru, Timnit},
  booktitle = {Proceedings of Machine Learning Research},
  volume = {81},
  pages = {1--15},
  year = {2018},
  organization = {PMLR}
}

@article{Pereira2019,
  title = {Using health chatbots for behavior change: A mapping study},
  author = {Pereira, Joao and Diaz, Oscar},
  journal = {Journal of Medical Systems},
  volume = {43},
  number = {5},
  pages = {135},
  year = {2019},
  publisher = {Springer}
}

@article{srinivasan2024comprehensive,
  title={Comprehensive study on bias in large language models},
  author={Srinivasan, Nitin and Perumalsamy, Kishore Kumar and Sridhar, Praveen Kumar and Rajendran, Gowthamaraj and Kumar, Adithyan Arun},
  journal={International Refereed Journal of Engineering and Science},
  volume={13},
  number={2},
  pages={77--82},
  year={2024}
}




@article{nieminen2025recommendations,
  title={Recommendations for Mental Health Chatbot Conversations: An Integrative Review},
  author={Nieminen, Heidi and Vartiainen, Anna-Kaisa and Bond, Raymond and Laukkanen, Emilia and Mulvenna, Maurice and Kuosmanen, Lauri},
  journal={Journal of Advanced Nursing},
  year={2025},
  publisher={Wiley Online Library}
}


@article{abd2021perceptions,
  title={Perceptions and opinions of patients about mental health chatbots: scoping review},
  author={Abd-Alrazaq, Alaa A and Alajlani, Mohannad and Ali, Nashva and Denecke, Kerstin and Bewick, Bridgette M and Househ, Mowafa},
  journal={Journal of medical Internet research},
  volume={23},
  number={1},
  pages={e17828},
  year={2021},
  publisher={JMIR Publications Toronto, Canada}
}



showing promise in complex domains like psychotherapy, where context, empathy, and ethical considerations are paramount [@Levine2022]. Early attempts at integrating AI into mental health interventions underscore both the potential and the pitfalls: small-scale deployments of conversational agents have demonstrated feasibility in delivering cognitive-behavioural strategies to young adults, but their efficacy still depends heavily on transparent, evidence-based reasoning [@Fitzpatrick2017].
