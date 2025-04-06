import os
from flask import Flask, render_template, request, redirect, url_for, session, flash,jsonify
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
from gemini_api import check_ingredient_safety
import firebase_admin
from firebase_admin import credentials, db, auth
from gemini_api import check_ingredient_safety, analyze_product_safety

# Initialize Flask
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Firebase
cred = credentials.Certificate("firebase_config.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://food-safety-app-5329a-default-rtdb.firebaseio.com'  # Replace with your URL
})

# Authentication Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            user = auth.create_user(email=email, password=password)
            db.reference(f'users/{user.uid}').set({
                'email': email,
                'profile': {
                    'conditions': '',
                    'allergies': '',
                    'dietary_preferences': ''
                }
            })
            session['user_id'] = user.uid
            flash('Registration successful! Please complete your profile.', 'success')
            return redirect(url_for('profile'))
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            user = auth.get_user_by_email(email)
            session['user_id'] = user.uid
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash('Invalid credentials. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Profile Management
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_ref = db.reference(f'users/{session["user_id"]}/profile')
    
    if request.method == 'POST':
        profile_data = {
            'age': request.form.get('age'),
            'gender': request.form.get('gender'),
            'conditions': request.form.get('conditions'),
            'allergies': request.form.get('allergies'),
            'dietary_preferences': request.form.get('dietary_preferences')
        }
        user_ref.update(profile_data)
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('index'))
    
    profile = user_ref.get() or {}
    return render_template('profile.html', profile=profile)

# Main Analysis
@app.route("/", methods=["GET", "POST"])
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_ref = db.reference(f'users/{session["user_id"]}')
    user_data = user_ref.get()
    profile = user_data.get('profile', {}) if user_data else {}
    
    ingredients = []
    safe_ingredients = []
    unsafe_ingredients = []
    recommendation = {
        'safety': None,
        'explanation': None,
        'alternatives': None
    }
    
    if request.method == "POST" and "image" in request.files:
        file = request.files["image"]
        if file.filename != '':
            # Process image
            filename = secure_filename(file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(image_path)
            ingredients = extract_text(image_path)
            os.remove(image_path)
            
            if ingredients and not ingredients[0].startswith("Error"):
                # Build health context
                health_context = []
                if profile.get('conditions'):
                    health_context.append(f"Medical Conditions: {profile['conditions']}")
                if profile.get('allergies'):
                    health_context.append(f"Allergies: {profile['allergies']}")
                if profile.get('dietary_preferences'):
                    health_context.append(f"Dietary Preferences: {profile['dietary_preferences']}")
                
                # Get safety analysis
                safety_response = check_ingredient_safety(
                    ingredients,
                    " | ".join(health_context) if health_context else "General Population"
                )
                
                # Parse response
                if safety_response and not safety_response.startswith("Error"):
                    lines = [line.strip() for line in safety_response.split('\n') if line.strip()]
                    
                    # Parse safe ingredients
                    if lines and lines[0].startswith('Safe:'):
                        safe_ingredients = [ing.strip() for ing in lines[0][5:].split(',') if ing.strip()]
                    
                    # Parse unsafe ingredients
                    unsafe_ingredients = []
                    for line in lines[1:]:
                        if line.startswith('Verdict:'):
                            break
                        if line.startswith('-'):
                            # More robust parsing of unsafe ingredients
                            parts = line[2:].strip().split('(')
                            if len(parts) > 1:
                                ingredient = parts[0].strip()
                                reason_part = parts[1].split(')')[0].strip()
                                unsafe_ingredients.append({
                                    'name': ingredient,
                                    'reason': reason_part,
                                    'alternative': line.split('→ Try:')[1].strip() if '→ Try:' in line else None
                                })
                    
                    # Parse recommendation
                    verdict_lines = [line for line in lines if line.startswith('- Recommendation:') or 
                                   line.startswith('- Explanation:') or 
                                   line.startswith('- Alternatives:')]
                    for line in verdict_lines:
                        if line.startswith('- Recommendation:'):
                            recommendation['safety'] = line.split(':')[1].strip()
                        elif line.startswith('- Explanation:'):
                            recommendation['explanation'] = line.split(':')[1].strip()
                        elif line.startswith('- Alternatives:'):
                            recommendation['alternatives'] = line.split(':')[1].strip()
    
    return render_template("index.html",
                         ingredients=ingredients,
                         safe_ingredients=safe_ingredients,
                         unsafe_ingredients=unsafe_ingredients,
                         recommendation=recommendation,
                         profile=profile)

# OCR Function
def extract_text(image_path):
    try:
        img = Image.open(image_path).convert("L")
        img = img.resize((img.width*3, img.height*3))
        img = img.filter(ImageFilter.MedianFilter(size=3))
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(3.5)
        img = img.point(lambda p: 0 if p < 160 else 255)
        
        text = pytesseract.image_to_string(img, config='--psm 6 --oem 3')
        text = re.sub(r'[^a-zA-Z0-9, ]+', '', text.replace("\n", " "))
        return [i.strip() for i in re.split(r',|\sand\s', text) if i.strip()]
    except Exception as e:
        return [f"OCR Error: {str(e)}"]


@app.route("/product-check", methods=["GET", "POST"])
def product_check():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_ref = db.reference(f'users/{session["user_id"]}')
    user_data = user_ref.get()
    profile = user_data.get('profile', {}) if user_data else {}
    
    product = ""
    analysis = None
    
    if request.method == "POST":
        product = request.form.get("product", "").strip()
        if product:
            # Build health context
            health_context = []
            if profile.get('conditions'):
                health_context.append(f"Medical Conditions: {profile['conditions']}")
            if profile.get('allergies'):
                health_context.append(f"Allergies: {profile['allergies']}")
            if profile.get('dietary_preferences'):
                health_context.append(f"Dietary Preferences: {profile['dietary_preferences']}")
            
            # Get safety analysis
            analysis = analyze_product_safety(
                product,
                " | ".join(health_context) if health_context else "General Population"
            )
    
    return render_template("product_check.html", 
                         product=product,
                         analysis=analysis,
                         profile=profile)

# Add this new route with existing imports
@app.route('/analyze-voice', methods=['POST'])
def analyze_voice():
    if 'user_id' not in session:
        return jsonify({"error": "Login required"}), 401

    try:
        data = request.get_json()
        product = data.get('product', '').strip()
        
        if not product:
            return jsonify({"error": "No product specified"}), 400

        # Get user's health context from Firebase
        health_context = []
        profile_ref = db.reference(f'users/{session["user_id"]}/profile')
        profile = profile_ref.get() or {}

        if profile.get('conditions'):
            health_context.append(f"Medical Conditions: {profile['conditions']}")
        if profile.get('allergies'):
            health_context.append(f"Allergies: {profile['allergies']}")

        # Use your existing Gemini analysis
        analysis = analyze_product_safety(
            product,
            " | ".join(health_context) if health_context else "General Population"
        )

        # Parse the Gemini response
        if "Safety Status: Safe" in analysis:
            verdict = "Safe"
        elif "Safety Status: Caution" in analysis:
            verdict = "Caution"
        else:
            verdict = "Avoid"

        # Extract details and alternatives
        concerns = analysis.split("Concerns:")[1].split("\n")[0].strip() if "Concerns:" in analysis else "No specific concerns"
        alternatives = analysis.split("Alternatives:")[1].strip() if "Alternatives:" in analysis else "None suggested"

        return jsonify({
            "product": product,
            "verdict": verdict,
            "details": concerns,
            "alternatives": alternatives
        })

    except Exception as e:
        print(f"Error in analyze_voice: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)