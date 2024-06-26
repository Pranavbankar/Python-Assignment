import graphene
from graphene import Boolean, ObjectType, String, Int, List, Field, InputObjectType, Mutation
from graphene_file_upload.scalars import Upload
import os
import json

# Load and save todos to a file
def load_todos():
    if os.path.exists('todos.json'):
        with open('todos.json', 'r') as file:
            return json.load(file)
    return []

def save_todos(todos):
    with open('todos.json', 'w') as file:
        json.dump(todos, file)

class TodoType(ObjectType):
    id = Int()
    title = String()
    desc = String()
    date = String()
    image = String()

class Query(ObjectType):
    todos = List(TodoType)

    def resolve_todos(root, info):
        return load_todos()

class CreateTodoInput(InputObjectType):
    title = String(required=True)
    desc = String()
    date = String()
    image = Upload()

class CreateTodoMutation(Mutation):
    class Arguments:
        input = CreateTodoInput(required=True)

    todo = Field(TodoType)

    def mutate(root, info, input):
        todos = load_todos()
        new_todo = {
            'id': len(todos) + 1,
            'title': input.title,
            'desc': input.desc,
            'date': input.date,
            'image': None
        }
        if input.image:
            image_path = os.path.join('static/images', input.image.filename)
            input.image.save(image_path)
            new_todo['image'] = image_path
        todos.append(new_todo)
        save_todos(todos)
        return CreateTodoMutation(todo=new_todo)

class UpdateTodoInput(InputObjectType):
    id = Int(required=True)
    title = String()
    desc = String()
    date = String()
    image = Upload()

class UpdateTodoMutation(Mutation):
    class Arguments:
        input = UpdateTodoInput(required=True)

    todo = Field(TodoType)

    def mutate(root, info, input):
        todos = load_todos()
        todo = next((todo for todo in todos if todo['id'] == input.id), None)
        if todo:
            todo['title'] = input.title if input.title else todo['title']
            todo['desc'] = input.desc if input.desc else todo['desc']
            todo['date'] = input.date if input.date else todo['date']
            if input.image:
                image_path = os.path.join('static/images', input.image.filename)
                input.image.save(image_path)
                todo['image'] = image_path
            save_todos(todos)
            return UpdateTodoMutation(todo=todo)
        return None

class DeleteTodoMutation(Mutation):
    class Arguments:
        id = Int(required=True)

    success = Boolean()

    def mutate(root, info, id):
        todos = load_todos()
        todos = [todo for todo in todos if todo['id'] != id]
        save_todos(todos)
        return DeleteTodoMutation(success=True)

class Mutation(ObjectType):
    create_todo = CreateTodoMutation.Field()
    update_todo = UpdateTodoMutation.Field()
    delete_todo = DeleteTodoMutation.Field()

schema = graphene.Schema(query=Query, mutation=Mutation)

