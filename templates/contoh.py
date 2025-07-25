# ====================== MODEL ======================
class UserModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(80), unique=True, nullable=False)

    def __repr__(self):
        return f"User(name={self.name}, email={self.email})"

with app.app_context():
    db.create_all()

# ====================== PARSER ======================
user_args = reqparse.RequestParser()
user_args.add_argument('name', type=str, required=True, help="Name cannot be blank!")
user_args.add_argument('email', type=str, required=True, help="Email cannot be blank!")

userFields = {
    'id': fields.Integer,
    'name': fields.String,
    'email': fields.String
}

# ====================== API RESOURCES ======================
class Users(Resource):
    @marshal_with(userFields)
    def get(self):
        users = UserModel.query.all()
        return users

    @marshal_with(userFields)
    def post(self):
        args = user_args.parse_args()
        user = UserModel(name=args["name"], email=args["email"])
        db.session.add(user)
        db.session.commit()
        return UserModel.query.all(), 201

class User(Resource):
    @marshal_with(userFields)
    def get(self, id):
        user = UserModel.query.filter_by(id=id).first()
        if not user:
            abort(404, "User Not Found")
        return user

    @marshal_with(userFields)
    def patch(self, id):
        args = user_args.parse_args()
        user = UserModel.query.filter_by(id=id).first()
        if not user:
            abort(404, "User Not Found")
        user.name = args["name"]
        user.email = args["email"]
        db.session.commit()
        return user

    @marshal_with(userFields)
    def delete(self, id):
        user = UserModel.query.filter_by(id=id).first()
        if not user:
            abort(404, "User Not Found")
        db.session.delete(user)
        db.session.commit()
        return UserModel.query.all(), 200

api.add_resource(Users, '/api/users/')
api.add_resource(User, '/api/users/<int:id>')