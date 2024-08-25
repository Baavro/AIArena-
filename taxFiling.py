from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Dict 
from decimal import Decimal
import openai
import ast
import re


class ITRDetails(BaseModel):
    Employment: str = Field(
        enum=["State Government Employ", "Public Sector Undertaking", "Pensioners-Central Government", "Pensioners-State Government", "Pensioners-Public Sector", "Pensioners-Others"],
        description="Nature of employment (fill your choice)",
        default=""  # Set the default value here
    )
    tax_regime: str = Field(
        enum=["Yes", "No"],
        description="Whether the user is opting for new tax regime u/s 115BAC (fill Yes or No)",
        default=""  # Set the default value here
    )
    seventh_proviso: str = Field(
        enum=["True", "False"],
        description="To be filled only if a person is not required to furnish a return of income under section 139(1) but filing return of income due to fulfilling one or more conditions mentioned in the seventh proviso to section 139(1)",
        default="False"
    )
    filled_under: str = Field(
        description="Section under which income tax is filled",
        enum=["139(1)"],
        default="139(1)"  # Set the default value here
    )
    salary_section_17_1: Decimal = Field(
        default = "",
        description="Salary as per section 17(1) (please enter numeric values only!)"
    )
    perquisites_value_section_17_2: Decimal = Field(
        default = "",
        description="Value of perquisites as per section 17(2) (please enter numeric values only!)"
    )
    profit_salary_section_17_3: Decimal = Field(
        default = "",
        description="Profit in lieu of salary as per section 17(3) (please enter numeric values only!)"
    )
    exempt_allowances_section_10: list = Field(
        default = "",
        description="Allowances to the extent exempt u/s 10, provide a list of applicable allowance from the options",
        enum = [""]
    )
    house_property_type: str = Field(
        default = "",
        description="Type of House Property (fill your choice)",
        enum = ["Self Occupied","Let out", "Deemed to let out"]
    )
    rent_received: Decimal = Field(
        default = "",
        description="Gross rent received/ receivable/ lettable value during the year (please enter numeric values only!)"
    )
    tax_paid_local_authorities: Decimal = Field(
        default = "",
        description="Tax paid to local authorities (please enter numeric values only!)"
    )
    interest_borrowed_capital: Decimal = Field(
        default = "",
        description="Interest payable on borrowed capital (please enter numeric values only!)"
    )
    arrears_received_less_30: Decimal = Field(
        default = "",
        description="Arrears/Unrealised Rent received during the year Less 30% (please enter numeric values only!)"
    )
    income_other_sources: list = Field(
        default = "",
        description="Income from Other Sources",
        enum = [""]
    )
    income_retirement_benefit_account: Dict[str, Decimal] = Field(
        default = "",
        description="Income from retirement benefit account maintained in a notified country u/s 89A (Quarterly breakup of Taxable Portion)"
    )
    exempt_income_agri: Decimal = Field(
        default = "",
        description="Exempt Income: For reporting purpose (please enter numeric values only!)",
        enum = ["Agricultural Income"]
    )
#Details of Tax Deducted at Source from SALARY [As per FORM 16 issued by Employer(s)]
#Details of Tax Deducted at Source from Income OTHER THAN Salary  [As per FORM 16 A issued by Deductor(s)]
#Details of Tax Deducted at Source [As per Form 16C furnished by the Payer(s)]
#Details of Advance tax and Self Assessment tax payments
#
#DETAILS OF TAX COLLECTED AT SOURCE [AS PER FORM 27D ISSUED BY THE COLLECTOR(S)]
#
#Details of all Bank Accounts held in India at any time during the previous year (excluding dormant accounts)


def smart_convert(value):
    converters = [
        int,
        float,
        complex,
        ast.literal_eval,  # Add support for dict and list
    ]

    # Remove leading and trailing whitespaces
    value = value.strip()

    # Remove any non-python code before or after the Python literal structure (if any)
    match = re.search(r'(\{.\}|\[.\])', value)
    if match:
        value = match.group(1)

    for converter in converters:
        try:
            return converter(value)
        except (ValueError, SyntaxError):
            pass

    # If no conversion was successful, return the original string
    return value

def prompt_template(question,options):
    prompt = f"You are an Indian tax assisstant. Help me file my Income Tax return (ITR1).\
        Below is the questions you need to ask the user. Explain the question to help me better understand and ease the process of filing ITR1. \n\
        Question: {question} \
        Options:{options}" 

    template =  'You are an Indian tax assisstant. Help me file my Income Tax return (ITR1) .Below is the questions to ask the user. Explain the question to help me better understand: \
Question: Nature of employment.\
Options: "State Government Employ", "Public Sector Undertaking", "Pensioners-Central Government", "Pensioners-State Government", "Pensioners-Public Sector", "Pensioners-Others"'
    return prompt

def keyword_template(question):
    prompt = f"""Extract the Keywords from the question and return a list of keywords, to later provide more information about the keyword.
    <START OF THE EXAMPLE>
    <Input>
    Whether you are opting for the new tax regime under section 115BAC? Please choose one of the following options: 
    1. True
    2. False
    <Output>
    ['section 115BAC']
    <END OF THE EXAMPLE>

    Here is the Input for you:
    Input: {question}
    Output:
    """
    return prompt

def response_template(response,option):
    prompt = f"""Based on the Response select the option that is most closely related to the response and return the option in a list. If the Options are None, Return the fincancial value as a float. 
    <START OF THE EXAMPLE>
    <Input>
    Response: I am working for a public sector company
    Options : 'State Government Employee', 'Public Sector Undertaking Employee', 'Pensioner - Central Government', 'Pensioner - State Government', 'Pensioner - Public Sector', 'Pensioner - Others']
    <Output>
    ['Public Sector Undertaking Employee']
    <END OF THE EXAMPLE>

    <START OF THE EXAMPLE>
    <Input>
    Response: My salary as per section 17(1) is 25,000 Indian Rupees
    Options : None
    <Output>
    25000
    <END OF THE EXAMPLE>

    Here is the Response and Option for you:
    Response: {response}
    Options: {option}
    """
    return prompt

def route(framed_question,response_user):    
    prompt = f"""Given a raw question and follow up on the question, determine whether the \
        follow-up is a "Query" or "Next" to the question.
        Query refers to any doubt or clarification user needs about a question,
        Next refers to going to the next section since user answered the question or is willing to go next. 
        Return the Keyword "Query" or "Next" in a list format
    
<< EXAMPLE 1>>
    << INPUT >>
    Question: Whether the user is opting for new tax regime u/s 115BAC
    Follow-up: Can you tell me more about 115BAC
    << OUTPUT >>
    ["Query"]

<< EXAMPLE 2>>
    << INPUT >>
    Question: Whether the user is opting for new tax regime u/s 115BAC
    Follow-up: Yes I am optiong for new regime
    << OUTPUT >>
    ["Next"]

<< EXAMPLE 3>>
    << INPUT >>
    Question:Is there anything else that you need assisstance with or we can move to the next section.
    Follow-up: Lets move ahead
    << OUTPUT >>
    ["Next"]

<< INPUT >>
Question: {framed_question}
Follow-up: {response_user}
<< OUTPUT >>
"""
    return prompt

def query_template(framed_question, response_user):
    prompt = f"""You are an Indian tax assisstant helping me file my Income Tax return (ITR1). 
    I need help with the following question:
    {framed_question}
    This is my query regarding the question:
    {response_user}
    Give me detailed answer to solve my query and ease the process of filling my ITR1."""
    return prompt
def generate_chat_completion(prompt: str) -> str:
        completion = openai.ChatCompletion.create(
          model="gpt-3.5-turbo",
          temperature = 0,
          max_tokens=256,
          messages=[
            {"role": "system", "content": prompt}
          ]
        )
        return completion.choices[0].message['content']

def generate_completion(prompt: str) -> str:
        completion = openai.Completion.create(
          model="text-davinci-003",
          temperature = 0,
          max_tokens=256,
          prompt=prompt
        )
        return completion.choices[0]['text']

userITR = ITRDetails()
data = []

for field_name, field in userITR.__fields__.items():
    if field.default == "" or field.default == None:
        question = field.field_info.description
        option = field.field_info.extra.get('enum')
        prompt = prompt_template(question,option) 
        framed_question = generate_chat_completion(prompt)
        keyword_prompt = keyword_template(framed_question)
        keywords = generate_completion(keyword_prompt)
        keywords = smart_convert(keywords)
        print(keywords)
        response_user = input(framed_question + "\n\n" + "Enter your answer: ")
        response_prompt = route(framed_question,response_user)
        response_route = generate_completion(response_prompt)
        response_route = smart_convert(response_route)
        if response_route[0] == "Query":
            while response_route[0] == "Query":
                query_prompt = query_template(framed_question, response_user)
                query_response = generate_chat_completion(query_prompt)
                print(query_response)
                next_sec = "Is there anything else that you need assisstance with or we can move to the next section."
                response_user = input(next_sec + "\n\n" + "Enter your answer: ")
                response_prompt = route(next_sec, response_user)
                response_route = generate_completion(response_prompt)
                response_route = smart_convert(response_route)
            response_user = input(framed_question)
            response_prompt = response_template(response_user,option)
            answer = generate_completion(response_prompt)
            result = smart_convert(answer)
            print(result)

        else:
            response_prompt = response_template(response_user,option)
            answer = generate_completion(response_prompt)
            result = smart_convert(answer)
            print(result)
    value = getattr(userITR, field_name)
    if value not in ["", None]:
        question = field.field_info.description
        data.append({"question": question, "answer": value})

print(data)    