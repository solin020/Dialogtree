
from xml.etree import ElementTree as ET
from openai import OpenAI
import textwrap


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
        choice = self.parent.complete(
            self.parent.substitute(
                self.answerparse, response=response, backprompt=backprompt
            )
        )
        print("choice", choice)
        while (pair:=findmatch(choice, self.jump_table)) is None:
            print(self.parent.complete(
                self.parent.substitute(self.errorprompt, response=response, backprompt=backprompt)
                ))
            response = input()
            choice = self.parent.complete(
                self.parent.substitute(
                    self.answerparse, response=response, backprompt=backprompt
                )
            )
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

class Goodbye:
    def __init__(self, node, parent):
        self.node = node
        self.parent = parent
    
    def execute(self):
        print(self.parent.substitute(self.node, self.parent.context))


class FullQuestion:
    def __init__(self, node, parent):
        self.node = node
        self.parent = parent
        children = list(node)
        if children[0].tag == "preamble":
            self.preamble, self.systemquestion, self.continuequestion, self.answerparse, *self.jumps = list(node)
        else:
            self.preamble = None
            self.systemquestion, self.continuequestion, self.answerparse, *self.jumps = list(node)
        self.jump_table = {}
        for j in self.jumps:
            for a in j.attrib['answer'].split(' '):
                self.jump_table[a] = j
    
    def execute(self):
        print('gothere')
        backprompt = None
        response = None
        if self.preamble is not None:
            backprompt = self.parent.substitute(self.preamble)
            print(backprompt)
            response = input()
        print(self.parent.complete(
            self.parent.substitute(self.systemquestion, backprompt=backprompt, response=response))
        )
        backprompt = self.parent.substitute(self.continuequestion, backprompt=backprompt, response=response)
        print(backprompt)
        response = input()
        choice = self.parent.complete(
                self.parent.substitute(
                    self.answerparse, response=response, backprompt=backprompt
                )
            )
        while (pair:=findmatch(choice, self.jump_table)) is None:
            print(
                self.parent.substitute(self.continuequestion, response)
                )
            response = input()
            choice = self.parent.complete(
                self.parent.substitute(
                    self.answerparse, response=response, backprompt=backprompt
                )
            )
        self.parent.jump(pair[0], pair[1])
        
def findmatch(choice, jump_table):
    for key, jump in jump_table.items():
        if key.lower() in choice.lower():
            return jump, key
        
        



class Dialog:
    def __init__(self, treefile, functions, openai_key, org_id, model="gpt-3.5-turbo"):
        self.parse(ET.parse(treefile).getroot())
        self.client = OpenAI(api_key=openai_key, organization=org_id)
        self.model = model
    
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
            case 'fullquestion': return FullQuestion(target_node, self)
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