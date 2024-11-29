from pyparsing import (
    Word,
    alphas,
    alphanums,
    delimitedList,
    Suppress,
    Group,
    Optional,
    QuotedString,
    Dict,
    ZeroOrMore,
    Literal,
    restOfLine,
    StringEnd,
    Combine,
    OneOrMore,
)


# Example input
example_text = """
You are an expert in behaviour change. You and the client 
are working on @problem.summary and @problem.elicited, which is the focus of this session.

// These are some examples which might be relevant:
@examples "a therapist reflecting a client's feelings" {search=rag}

// These examples are related to the client's problem: @examples @problem.summary.

This is your clinical formulation of the case: @data.formulation.

This is what has been said recently: @history.all{n=30}.

Think about what you would say next. Consider all perspectives:

[[think:approach]]

Now, say something to the client. Keep it simple.

[[speak:response]]
"""


quoted_string = QuotedString('"')  # Strings in double quotes

# Basic building blocks
identifier = Word(alphas, alphanums + "_")  # Variable or function names

keyword_args = Group(
    OneOrMore(
        Group(identifier("key") + Suppress("=") + (quoted_string | Word(alphanums + "_"))("value"))
        + Optional(Suppress(","))
    )
)("keyword_args")

xx = keyword_args.parseString("xxx=yyy,zzz=111" "")
xx.keyword_args[1].value == "111"


def add_metadata(tokens):
    tokens["metadata"] = {"parsed_by": "custom_parser", "timestamp": "2024-11-28"}
    return tokens


from collections import namedtuple

Response = namedtuple("Response", ["action", "variable_name", "keyword_args"])

ai_response = (
    Group(
        Suppress("[[")
        + identifier("action")
        + Suppress(":")
        + Optional(identifier("variable_name"))
        + Optional(Literal("|") + keyword_args)
        + Suppress("]]")
    )
    .addParseAction(
        lambda tokens: Response(
            tokens[0].action, tokens[0].variable_name, keyword_args=tokens[0].keyword_args
        )
    )
    .setResultsName("RESPONSE", listAllMatches=True)
)

other = Word(alphas + alphanums + ".,!?\"'()- \n")  # Allow newline in other
parts = OneOrMore(ai_response | other)

res = parts.parseString(
    """Hellow [[think:approach|xxx=yyy,zzz=111]] world
This is secon [[speak:now]]"""
)
list(res.keys())


res[1]
