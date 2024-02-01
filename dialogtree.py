
from xml.etree import ElementTree as ET
from openai import OpenAI
import textwrap
from loguru import logger
import argparse
import sys
parser = argparse.ArgumentParser()
parser.add_argument(
    '-d', '--debug',
    help="Print lots of debugging statements",
    action="store_const", dest="loglevel", const='DEBUG',
    default='WARNING',
)
args = parser.parse_args() 
logger.remove(0)
logger.add(sys.stderr, level=args.loglevel)   


class Branch:
    def __init__(self, node, parent):
        self.node = node
        self.parent = parent
        self.prompt, self.errorprompt, self.answerparse, *self.jumps = node
        self.jump_table = {}
        for j in self.jumps:
            for a in j.attrib['answer'].split(' '):
                self.jump_table[a] = j

    
    def execute(self):
        backprompt = self.parent.substitute(self.prompt)
        print(backprompt)
        response = input()
        answerparse_prompt = self.parent.substitute(
            self.answerparse, response=response, backprompt=backprompt
        )
        logger.debug(f"{answerparse_prompt=}")
        choice = self.parent.complete(answerparse_prompt)
        logger.debug(f"attempted parse: {choice}")
        while (pair:=findmatch(choice, self.jump_table)) is None:
            error_prompt = self.parent.substitute(self.errorprompt, response=response, backprompt=backprompt)
            logger.debug(f"{error_prompt=}")
            print(self.parent.complete(error_prompt))
            response = input()
            answerparse_prompt = self.parent.substitute(
                self.answerparse, response=response, backprompt=backprompt
            )
            logger.debug(f"{answerparse_prompt=}")
            choice = self.parent.complete(answerparse_prompt)
            logger.debug(f"attempted parse: {choice}")
        logger.debug(f"parsed answer: {pair[0]}")
        self.parent.jump(pair[0], pair[1])



        


class State:
    def __init__(self, node, parent):
        self.node = node
        self.parent = parent
    
    def execute(self):
        print(self.parent.substitute(self.node, self.parent.context))
        if 'nextdestination' in self.node.attrib:
            self.parent.jump_destinations[self.node.attrib['nextdestination']].execute()
        else:
            self.parent.jump_destinations['end'].execute()

class LLMQuestionDirect:
    def __init__(self, node, parent):
        self.node = node
        self.parent = parent
    
    def execute(self):
        llm_input = self.parent.substitute(self.node, self.parent.context)
        logger.debug(f"{llm_input=}")
        print(self.parent.complete(llm_input))
        if 'nextdestination' in self.node.attrib:
            self.parent.jump_destinations[self.node.attrib['nextdestination']].execute()
        else:
            self.parent.jump_destinations['end'].execute()

class LLMQuestionIndirect:
    def __init__(self, node, parent):
        self.node = node
        self.parent = parent
        self.userquestion, self.answerparse = node
    
    def execute(self):
        backprompt = self.parent.substitute(self.userquestion)
        print(backprompt)
        response = input()
        answerparse_prompt = self.parent.substitute(
            self.answerparse, response=response, backprompt=backprompt
        )
        logger.debug(f"{answerparse_prompt=}")
        print(self.parent.complete(answerparse_prompt))
        if 'nextdestination' in self.node.attrib:
            self.parent.jump_destinations[self.node.attrib['nextdestination']].execute()
        else:
            self.parent.jump_destinations['end'].execute()

class Goodbye:
    def __init__(self, node, parent):
        self.node = node
        self.parent = parent
    
    def execute(self):
        print(self.parent.substitute(self.node, self.parent.context))


        
def findmatch(choice, jump_table):
    for key, jump in jump_table.items():
        if key.lower() in choice.lower():
            return jump, key
        
        



class Dialog:
    from typing import Callable
    def __init__(self, treefile:str, functions:dict[str, Callable], openai_key:str, org_id:str, model:str="gpt-3.5-turbo"):
        self.parse(ET.parse(treefile).getroot())
        self.functions=functions
        self.client = OpenAI(api_key=openai_key, organization=org_id)
        self.model = model
    
    def __init_subclass__(self, treefile:str, functions:dict[str, Callable], *args, **kwargs):
        self.parse(ET.parse(treefile).getroot())
        self.functions=functions

    
    def parse(self, root):
        self.root = root
        self.targets = [self.parse_target(tn) for tn in root]
        self.start_target = self.targets[0]
        self.jump_destinations = {}
        for t in self.targets:
            if 'destinationname' in t.node.attrib:
                self.jump_destinations[t.node.attrib['destinationname']] = t
    
    def jump(self, node, answer=""):
        possible_destination = self.execute_jump_function(node, answer)
        if 'nextdestination' in node.attrib:
            possible_destination = node.attrib['nextdestination']
        print('destination', possible_destination)
        if possible_destination not in self.jump_destinations:
            print(f'Invalid destination: {possible_destination}, restarting')
            self.start()
        else:
            self.jump_destinations[possible_destination].execute()
    
    def execute_jump_function(self, node, answer):
        if 'function_name' in node.attrib:
            return self.functions[node.attrib['function_name']](answer, self.context)
        elif (node.text is not None) and node.text.strip():
            ldict = {}
            exec("def jfun(answer, context):\n" +
                        textwrap.indent(textwrap.dedent(node.text).strip(), prefix='    '), globals(), ldict)
            return ldict['jfun'](answer, self.context)


    
    def parse_target(self, target_node):
        match target_node.tag:
            case 'state': return State(target_node, self)
            case 'branch': return Branch(target_node, self)
            case 'llmquestion-indirect': return LLMQuestionIndirect(target_node, self)
            case 'llmquestion-direct': return LLMQuestionDirect(target_node, self)
            case 'goodbye': return Goodbye(target_node, self)

    def substitute(self, node, response=None, backprompt=None):
        start = node.text
        for item in node:
            if item.tag == 'response':
                start += response
            elif item.tag == 'backprompt':
                start += backprompt
            elif item.tag == 'context':
                start += self.context[item.attrib['key']]
            start += item.tail
        return '\n'.join(s.strip() for s in start.split('\n'))
        
    def start(self):
        self.context = {}
        self.start_target.execute()
    
    def complete(self, prompt):
        #print('asked bot', prompt) #disable when not debugging
        chat_completion = self.client.chat.completions.create(
        messages=[
                 {
                     "role": "user",
                     "content": "Don't be verbose. " + prompt,
                 }
             ],
             model=self.model,
        )
        return chat_completion.choices[0].message.content