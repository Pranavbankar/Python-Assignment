from flask import Flask, make_response, render_template, request, redirect, url_for, session
from keycloak import keycloak_openid
from functools import wraps
import os
import json
import graphene
from graphene import Boolean, ObjectType, String, Int, List, Field, InputObjectType, Mutation
from graphene_file_upload.scalars import Upload

app = Flask(__name__)
app.secret_key = 'YOUR_SECRET_KEY'  # Replace with your secret key

app.config['UPLOAD_FOLDER'] = 'static/images'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# Keycloak Configuration
keycloak_openid = keycloak_openid.KeycloakOpenID(
    server_url="http://localhost:8080/",
    client_id="flask-app",
    realm_name="todo-app",
    client_secret_key= "P2PUOfncxEnNhdqMLIuo99UPYZsridlT",   #use your client_secret_key
    verify=True
)
def validate_token(token):
    return keycloak_openid.decode_token(token)

def load_todos(user_id):
    file_path = f'todos_{user_id}.json'
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)
    return []

def save_todos(todos, user_id):
    file_path = f'todos_{user_id}.json'
    with open(file_path, 'w') as file:
        json.dump(todos, file)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'token' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login')
def login():
    redirect_uri = url_for('callback', _external=True)
    return redirect(keycloak_openid.auth_url(redirect_uri=redirect_uri))

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token = keycloak_openid.token(grant_type='authorization_code', code=code, redirect_uri=url_for('callback', _external=True))
    session['token'] = token
    session['userinfo'] = keycloak_openid.userinfo(token['access_token'])
    return redirect(url_for('dashboard'))

@app.route('/register-callback')
def register_callback():
    return redirect(url_for('index'))



 
@app.route('/logout')
def logout():
    # Get the token from session
    token = session.get('token')
    if token:
        # Perform Keycloak logout
        keycloak_openid.logout(token['refresh_token'])
        
        # Clear the session
        session.clear()
        
        # Create a response object
        response = make_response(redirect(url_for('index')))
        
        # Clear the cookies
        response.set_cookie('session', '', expires=0)
        response.set_cookie('session.sig', '', expires=0)
        
        return response
    return redirect(url_for('index'))



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['userinfo']['sub']
    todos = load_todos(user_id)
    return render_template('dashboard.html', todos=todos)



@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_todo():
    user_id = session['userinfo']['sub']
    if request.method == 'POST':
        todos = load_todos(user_id)
        new_todo = {
            'id': len(todos) + 1,
            'title': request.form['title'],
            'desc': request.form['desc'],
            'date': request.form['date'],
            'image': None
        }

        # Restrict image uploads to Pro users
        if 'image' in request.files:
            if session.get('is_pro'):
                image = request.files['image']
                if image.filename:
                    image_path = os.path.join('static/images', image.filename)
                    image.save(image_path)
                    new_todo['image'] = image_path
            else:
                return "You need to purchase a Pro license to upload images."

        todos.append(new_todo)
        save_todos(todos, user_id)
        return redirect(url_for('index'))
    return render_template('add_todo.html')


@app.route('/edit/<int:todo_id>', methods=['GET', 'POST'])
@login_required
def edit_todo(todo_id):
    user_id = session['userinfo']['sub']
    todos = load_todos(user_id)
    todo = next((todo for todo in todos if todo['id'] == todo_id), None)
    if request.method == 'POST':
        if todo:
            todo['title'] = request.form['title']
            todo['desc'] = request.form['desc']
            todo['date'] = request.form['date']
            if 'image' in request.files:
                image = request.files['image']
                if image.filename:
                    image_path = os.path.join('static/images', image.filename)
                    image.save(image_path)
                    todo['image'] = image_path
            save_todos(todos, user_id)
        return redirect(url_for('dashboard'))
    return render_template('edit_todo.html', todo=todo)

@app.route('/delete/<int:todo_id>', methods=['POST'])
@login_required
def delete_todo(todo_id):
    user_id = session['userinfo']['sub']
    todos = load_todos(user_id)
    todos = [todo for todo in todos if todo['id'] != todo_id]
    save_todos(todos, user_id)
    return redirect(url_for('dashboard'))


#stripe

import stripe
from flask import session

# Set your secret key. Remember to replace this with your actual secret key.
stripe.api_key = 'sk_test_51PUigWEi7jnlyTT5Ni6MASmcazw3irG9TxxK2oP8Ww98kMV4cbQm2z7YLlvQgsMbvhuCXXCVwAonzUGh4I3y4v4n00I202M0zS'

# Stripe Publishable Key
STRIPE_PUBLISHABLE_KEY = 'pk_test_51PUigWEi7jnlyTT5U63btQpin2QTLCQ7zaQXKNCd8W9mOnTTcnhzjb2BLPjTcJM2K0jlrjnVbAF46J7Y6fPbmfzO00Cbyr2eHk'

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Pro License',
                    },
                    'unit_amount': 2000,  # $20.00
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('pro_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('pro_cancel', _external=True),
        )
        return {'id': checkout_session.id}
    except Exception as e:
        return str(e), 403
    
@app.route('/checkout-complete', methods=['POST'])
def checkout_complete():
    # Logic to handle successful checkout
    session['is_pro'] = True
    # Redirect to dashboard or wherever appropriate
    return redirect(url_for('dashboard')) 



@app.route('/pro-success')
def pro_success():
    session_id = request.args.get('session_id')
    session['is_pro'] = True
    return redirect(url_for('dashboard'))

@app.route('/pro-cancel')
def pro_cancel():
    return redirect(url_for('index'))

#end of payment

# GraphQL Schema
class TodoType(ObjectType):
    id = Int()
    title = String()
    desc = String()
    date = String()
    image = String()

class Query(ObjectType):
    todos = List(TodoType)

    def resolve_todos(root, info):
        user_id = info.context['user_id']
        return load_todos(user_id)

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
        user_id = info.context['user_id']
        todos = load_todos(user_id)
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
        save_todos(todos, user_id)
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
        user_id = info.context['user_id']
        todos = load_todos(user_id)
        todo = next((todo for todo in todos if todo['id'] == input.id), None)
        if todo:
            todo['title'] = input.title if input.title else todo['title']
            todo['desc'] = input.desc if input.desc else todo['desc']
            todo['date'] = input.date if input.date else todo['date']
            if input.image:
                image_path = os.path.join('static/images', input.image.filename)
                input.image.save(image_path)
                todo['image'] = image_path
            save_todos(todos, user_id)
            return UpdateTodoMutation(todo=todo)
        return None

class DeleteTodoMutation(Mutation):
    class Arguments:
        id = Int(required=True)

    success = Boolean()

    def mutate(root, info, id):
        user_id = info.context['user_id']
        todos = load_todos(user_id)
        todos = [todo for todo in todos if todo['id'] != id]
        save_todos(todos, user_id)
        return DeleteTodoMutation(success=True)

class Mutation(ObjectType):
    create_todo = CreateTodoMutation.Field()
    update_todo = UpdateTodoMutation.Field()
    delete_todo = DeleteTodoMutation.Field()

schema = graphene.Schema(query=Query, mutation=Mutation)

@app.route('/graphql', methods=['POST'])
@login_required
def graphql_server():
    data = json.loads(request.data)
    user_id = session['userinfo']['sub']
    context = {'user_id': user_id}
    result = schema.execute(data.get('query'), context=context, variables=data.get('variables'))
    return json.dumps(result.data)

if __name__ == '__main__':
    app.run(debug=True)
