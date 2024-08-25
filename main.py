from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Dict 
from decimal import Decimal
import openai
import ast
import re
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)


def prompt_template(question,options):
    prompt = f"You are an Indian tax assisstant. Help me file my Income Tax return (ITR1).\
        Below is the questions you need to ask the user. Explain the question to help me better understand and ease the process of filing ITR1. \n\
        Question: {question} \
        Options:{options}" 
    #print(prompt)
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
    prompt = f"""Given question and follow up on the question, determine whether the \
        follow-up is a "Query" or "Answer" to the question.
        Query refers to any doubt or clarification user needs about a question,
        Answer refers to going to the next section since user answered the question or is willing to go next. 
        Return the Keyword "Query" or "Answer" in a list format
    
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
    ["Answer"]

<< EXAMPLE 3>>
    << INPUT >>
    Question:Is there anything else that you need assisstance with or we can move to the next section.
    Follow-up: Lets move ahead
    << OUTPUT >>
    ["Answer"]

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
    #print(prompt)
    return prompt

class ITRDetails(BaseModel):
    Employment: str = Field(
        enum=["State Government Employ", "Public Sector Undertaking", "Pensioners-Central Government", "Pensioners-State Government", "Pensioners-Public Sector", "Pensioners-Others"],
        description="Nature of employment",
        default=""  # Set the default value here
    )
    tax_regime: str = Field(
        enum=["Yes", "No"],
        description="Whether the user is opting for new tax regime u/s 115BAC",
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
        description="Salary as per section 17(1)"
    )
    perquisites_value_section_17_2: Decimal = Field(
        default = "",
        description="Value of perquisites as per section 17(2)"
    )
    profit_salary_section_17_3: Decimal = Field(
        default = "",
        description="Profit in lieu of salary as per section 17(3)"
    )
    exempt_allowances_section_10: list = Field(
        default = "",
        description="Allowances to the extent exempt u/s 10, provide a list of applicable allowance from the options",
        enum = [""]
    )
    house_property_type: str = Field(
        default = "",
        description="Type of House Property",
        enum = ["Self Occupied","Let out", "Deemed to let out"]
    )
    rent_received: Decimal = Field(
        default = "",
        description="Gross rent received/ receivable/ lettable value during the year"
    )
    tax_paid_local_authorities: Decimal = Field(
        default = "",
        description="Tax paid to local authorities"
    )
    interest_borrowed_capital: Decimal = Field(
        default = "",
        description="Interest payable on borrowed capital"
    )
    arrears_received_less_30: Decimal = Field(
        default = "",
        description="Arrears/Unrealised Rent received during the year Less 30%"
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
        description="Exempt Income: For reporting purpose",
        enum = ["Agricultural Income"]
    )

class ITRAssistant:
    def __init__(self, userITR):
        self.userITR = userITR
        self.current_field_index = 0  # Start at -1 so the first increment brings it to 0
        self.fields = [field for field_name, field in userITR.__fields__.items() if field.default == "" or field.default == None]

    def get_question_and_option(self):
        field = self.fields[self.current_field_index]
        question = field.field_info.description
        option = field.field_info.extra.get('enum')
        return question, option

    def generate_framed_question(self, prompt_template):
        question, option = self.get_question_and_option()
        prompt = prompt_template(question,option) 
        framed_question = generate_chat_completion(prompt)
        return framed_question

    def get_keywords(self, keyword_template, framed_question):
        keyword_prompt = keyword_template(framed_question)
        keywords = generate_completion(keyword_prompt)
        keywords = smart_convert(keywords)
        #print(keywords)
        return keywords

    def route_response(self, route, response_user):
        framed_question = self.generate_framed_question(prompt_template)
        response_prompt = route(framed_question,response_user)
        response_route = generate_completion(response_prompt)
        response_route = smart_convert(response_route)
        #print(response_route)
        return response_route, framed_question

    def generate_answer(self, response_template, response_user):
        question, option = self.get_question_and_option()
        response_prompt = response_template(response_user,option)
        answer = generate_completion(response_prompt)
        return answer

    def process_user_input(self, user_input, prompt_template, keyword_template, route, query_template, response_template):
        response_route, framed_question = self.route_response(route, user_input)
        if response_route[0] == "Query":
            #raise Exception("Queries are not supported in this configuration")
            query_prompt = query_template(framed_question, user_input)
            query_response = generate_chat_completion(query_prompt)
            query_response = smart_convert(query_response)
            #print(query_response)
            next_sec = "Is there anything else that you need assisstance with or we can move to the next section."
            self.current_field_index -= 1
            return query_response,next_sec,[]

        answer = self.generate_answer(response_template, user_input)
        answer = smart_convert(answer)
        #print(answer)
        field_name = self.fields[self.current_field_index].name
        setattr(self.userITR, field_name, answer)
        
        self.current_field_index += 1

        if self.current_field_index >= len(self.fields):
            next_question = None
            keywords = None
        else:
            next_question = self.generate_framed_question(prompt_template)
            keywords = self.get_keywords(keyword_template, next_question)

        return answer, next_question, keywords

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
    match = re.search(r'(\{.*\}|\[.*\])', value)
    if match:
        value = match.group(1)

    for converter in converters:
        try:
            return converter(value)
        except (ValueError, SyntaxError):
            pass

    # If no conversion was successful, return the original string
    return value

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
# Creating an instance of ITRDetails with default values

userITR = ITRDetails()
assistant = ITRAssistant(userITR)

#print("The question \"Nature of employment\" refers to the type of job or work you are currently engaged in. Please select the option that best describes your employment status from the following options:\n\n1. State Government Employee: If you are currently employed by the state government.\n\n2. Public Sector Undertaking: If you are working for a government-owned corporation or company.\n\n3. Pensioners - Central Government: If you are a retired employee of the central government and receiving a pension.\n\n4. Pensioners - State Government: If you are a retired employee of the state government and receiving a pension.\n\n5. Pensioners - Public Sector: If you are a retired employee of a public sector undertaking and receiving a pension.\n\n6. Pensioners - Others: If you are a retired employee from any other organization and receiving a pension.\n\nPlease select the option that applies to your current employment status.")

global flag
flag = 0
@app.route('/', methods=['GET','POST'])
def start():
    print("This is getting executed")
    global flag
    if flag >= 1:
        flag += 1
        if request.method == 'POST':
            print("Post Only")
            # data = request.get_json(force=True)
            input = request.form['name']
            # user_input = data['user_input']
            user_input=input
            answer, next_question, keywords = assistant.process_user_input(
                user_input, prompt_template, keyword_template, route, query_template, response_template)
            data={
                'answer': answer,
                'next_question': next_question,
                'keywords': keywords
            }
            return jsonify(data)
        return render_template('index.html')
    
    flag +=1
    return render_template('index.html')
#@app.route('/question', methods=['POSt'])
#def question():
#    data = request.get_json(force=True)
#    user_input = data['user_input']
#    answer, next_question, keywords = assistant.process_user_input(user_input, prompt_template, keyword_template, route, query_template, response_template)
#
#    return jsonify({
#        'answer': answer, 
#        'next_question': next_question, 
#        'keywords': keywords
#    })

#print("The question \"Nature of employment\" refers to the type of job or work you are currently engaged in. Please select the option that best describes your employment status from the following options:\n\n1. State Government Employee: If you are currently employed by the state government.\n\n2. Public Sector Undertaking: If you are working for a government-owned corporation or company.\n\n3. Pensioners - Central Government: If you are a retired employee of the central government and receiving a pension.\n\n4. Pensioners - State Government: If you are a retired employee of the state government and receiving a pension.\n\n5. Pensioners - Public Sector: If you are a retired employee of a public sector undertaking and receiving a pension.\n\n6. Pensioners - Others: If you are a retired employee from any other organization and receiving a pension.\n\nPlease select the option that applies to your current employment status.")
# Greeting the user and providing the first question
#@app.route('/', methods=['GET'])
#def start():
#    greet_message = "Hello, let's start the process. Please answer the following questions."
#    next_question = assistant.generate_framed_question(prompt_template)
#    keywords = assistant.get_keywords(keyword_template, next_question)
#    
#    return jsonify({
#        'answer': greet_message, 
#        'next_question': next_question, 
#        'keywords': keywords
#    })

@app.route('/filled_fields')
def filled_fields():
    # Assume we have an instance of UserITR

    # Prepare the data in a question-answer format
    data = []
    for field_name, field in userITR.__fields__.items():
        value = getattr(userITR, field_name)
        if value not in ["", None]:
            question = field.field_info.description
            data.append({"question": question, "answer": value})

    return jsonify(data)
if __name__ == '__main__':
    app.run(debug=True)