import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client
from datetime import datetime

app = Flask(__name__, template_folder='templates', static_folder='../public/static')
app.secret_key = os.environ.get('SECRET_KEY', 'boubel_saas_secret_key_2026')

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

def get_supabase_client():
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            print(f"Erreur Supabase: {e}")
            return None
    return None

# --- ROUTE SPÉCIALE DE RÉPARATION / RÉINITIALISATION ---
@app.route('/reset-admin')
def reset_admin():
    supabase = get_supabase_client()
    if not supabase:
        return "❌ Erreur : Les variables SUPABASE_URL ou SUPABASE_KEY ne sont pas lues sur Vercel."

    mdp_clair = "#M@meF@llou999#"
    hash_mdp = generate_password_hash(mdp_clair)

    try:
        res = supabase.table('utilisateurs').select('*').eq('identifiant', 'superadmin').execute()
        if res.data:
            supabase.table('utilisateurs').update({'mot_de_passe': hash_mdp}).eq('identifiant', 'superadmin').execute()
            return f"<h3>✅ Succès !</h3><p>Le mot de passe du <b>superadmin</b> a été réinitialisé en base.</p><ul><li><b>Identifiant :</b> superadmin</li><li><b>Mot de passe :</b> {mdp_clair}</li></ul><br><a href='/'>👉 Cliquer ici pour aller à la page de connexion</a>"
        else:
            supabase.table('utilisateurs').insert({
                'quincaillerie_id': None,
                'identifiant': 'superadmin',
                'mot_de_passe': hash_mdp,
                'role': 'super_admin'
            }).execute()
            return f"<h3>✅ Succès !</h3><p>Le compte <b>superadmin</b> a été créé.</p><ul><li><b>Identifiant :</b> superadmin</li><li><b>Mot de passe :</b> {mdp_clair}</li></ul><br><a href='/'>👉 Cliquer ici pour aller à la page de connexion</a>"
    except Exception as e:
        return f"<h3>❌ Erreur Supabase :</h3><p>{str(e)}</p>"

@app.route('/')
def index():
    produits, ventes, liste_quincailleries = [], [], []
    alertes_count = 0
    info_quincaillerie = None
    supabase = get_supabase_client()

    if session.get('connecte') and supabase:
        role = session.get('role')
        q_id = session.get('quincaillerie_id')

        # Si SUPER ADMIN
        if role == 'super_admin':
            res_q = supabase.table('quincailleries').select('*').order('id').execute()
            liste_quincailleries = res_q.data or []
            
            # Récupérer les identifiants des gérants pour chaque quincaillerie
            res_u = supabase.table('utilisateurs').select('id, quincaillerie_id, identifiant').eq('role', 'gerant').execute()
            users_map = {u['quincaillerie_id']: u['identifiant'] for u in (res_u.data or []) if u.get('quincaillerie_id')}
            
            for q in liste_quincailleries:
                q['identifiant_gerant'] = users_map.get(q['id'], 'Non attribué')

            return render_template(
                'super_admin.html',
                quincailleries=liste_quincailleries,
                total_clients=len(liste_quincailleries)
            )

        # Si GERANT DE QUINCAILLERIE
        elif q_id:
            res_q = supabase.table('quincailleries').select('*').eq('id', q_id).execute()
            if res_q.data:
                info_quincaillerie = res_q.data[0]
                if not info_quincaillerie.get('actif'):
                    session.clear()
                    flash("Votre compte est suspendu. Veuillez contacter l'administrateur.", "danger")
                    return redirect(url_for('index'))

            res_stock = supabase.table('stock').select('*').eq('quincaillerie_id', q_id).order('nom').execute()
            for item in (res_stock.data or []):
                stk = item.get('quantite', 0)
                seuil = item.get('seuil_alerte', 5)
                if stk <= seuil:
                    alertes_count += 1
                produits.append({
                    'id': item.get('id'),
                    'nom_affichage': item.get('nom'),
                    'stock_total': stk,
                    'prix_unitaire': float(item.get('prix_unitaire', 0)),
                    'seuil_alerte': seuil
                })

            res_ventes = supabase.table('ventes').select('*').eq('quincaillerie_id', q_id).order('created_at', desc=True).execute()
            for v in (res_ventes.data or []):
                ventes.append({
                    'id': v.get('id'),
                    'date_vente': v.get('date_vente'),
                    'nom_produit': v.get('nom_produit'),
                    'quantite_vendue': v.get('quantite_vendue'),
                    'prix_vente': float(v.get('prix_vente', 0)),
                    'vendu_par': v.get('vendu_par')
                })

    return render_template(
        'index.html',
        produits=produits,
        ventes=ventes,
        alertes_count=alertes_count,
        info_quincaillerie=info_quincaillerie
    )

@app.route('/login', methods=['POST'])
def login():
    identifiant = request.form.get('identifiant', '').strip()
    mot_de_passe = request.form.get('mot_de_passe', '').strip()
    supabase = get_supabase_client()

    if not supabase:
        flash("La connexion à la base de données n'est pas configurée.", "danger")
        return redirect(url_for('index'))

    res = supabase.table('utilisateurs').select('*').eq('identifiant', identifiant).execute()
    users = res.data or []

    if users and check_password_hash(users[0]['mot_de_passe'], mot_de_passe):
        user = users[0]
        session['connecte'] = True
        session['user_id'] = user['id']
        session['nom_utilisateur'] = user['identifiant']
        session['role'] = user['role']
        session['quincaillerie_id'] = user.get('quincaillerie_id')
        flash(f"Bienvenue, {identifiant} !", "success")
    else:
        flash("Identifiant ou mot de passe incorrect.", "danger")

    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for('index'))

# --- ESPACE SUPER ADMIN ---

@app.route('/admin/creer-quincaillerie', methods=['POST'])
def creer_quincaillerie():
    supabase = get_supabase_client()
    if session.get('role') != 'super_admin' or not supabase:
        return redirect(url_for('index'))

    nom_entreprise = request.form.get('nom_entreprise', '').strip()
    telephone = request.form.get('telephone', '').strip()
    identifiant_gerant = request.form.get('identifiant_gerant', '').strip()
    mdp_gerant = request.form.get('mdp_gerant', '').strip()

    res_q = supabase.table('quincailleries').insert({
        'nom_entreprise': nom_entreprise,
        'telephone': telephone,
        'actif': True
    }).execute()

    if res_q.data:
        new_q_id = res_q.data[0]['id']
        hashed_mdp = generate_password_hash(mdp_gerant)
        supabase.table('utilisateurs').insert({
            'quincaillerie_id': new_q_id,
            'identifiant': identifiant_gerant,
            'mot_de_passe': hashed_mdp,
            'role': 'gerant'
        }).execute()
        flash(f"Accès créé avec succès pour '{nom_entreprise}' !", "success")

    return redirect(url_for('index'))

@app.route('/admin/modifier-gerant/<int:q_id>', methods=['POST'])
def modifier_gerant(q_id):
    supabase = get_supabase_client()
    if session.get('role') != 'super_admin' or not supabase:
        return redirect(url_for('index'))

    nouvel_identifiant = request.form.get('identifiant_gerant', '').strip()
    nouveau_mdp = request.form.get('mdp_gerant', '').strip()

    res_u = supabase.table('utilisateurs').select('id').eq('quincaillerie_id', q_id).eq('role', 'gerant').execute()
    users = res_u.data or []

    if users:
        user_id = users[0]['id']
        update_data = {}
        if nouvel_identifiant:
            update_data['identifiant'] = nouvel_identifiant
        if nouveau_mdp:
            update_data['mot_de_passe'] = generate_password_hash(nouveau_mdp)

        if update_data:
            supabase.table('utilisateurs').update(update_data).eq('id', user_id).execute()
            flash("Identifiants du gérant mis à jour avec succès !", "success")
    else:
        flash("Aucun gérant trouvé pour cette quincaillerie.", "danger")

    return redirect(url_for('index'))

@app.route('/admin/toggle-quincaillerie/<int:id>')
def toggle_quincaillerie(id):
    supabase = get_supabase_client()
    if session.get('role') != 'super_admin' or not supabase:
        return redirect(url_for('index'))

    res = supabase.table('quincailleries').select('actif').eq('id', id).execute()
    if res.data:
        etat_actuel = res.data[0]['actif']
        supabase.table('quincailleries').update({'actif': not etat_actuel}).eq('id', id).execute()
        flash("Statut du compte mis à jour.", "info")

    return redirect(url_for('index'))

@app.route('/admin/supprimer-quincaillerie/<int:id>')
def supprimer_quincaillerie(id):
    supabase = get_supabase_client()
    if session.get('role') != 'super_admin' or not supabase:
        return redirect(url_for('index'))

    supabase.table('quincailleries').delete().eq('id', id).execute()
    flash("Quincaillerie et toutes ses données supprimées définitivement.", "info")
    return redirect(url_for('index'))

# --- ESPACE QUINCAILLERIE (CLIENT) ---

@app.route('/ajouter-stock', methods=['POST'])
def ajouter_stock():
    supabase = get_supabase_client()
    q_id = session.get('quincaillerie_id')
    if not session.get('connecte') or not q_id or not supabase:
        return redirect(url_for('index'))

    nom = request.form.get('nom', '').strip()
    quantite = int(request.form.get('quantite', 0))
    prix = float(request.form.get('prix', 0.0))
    seuil = int(request.form.get('seuil_alerte', 5))

    res = supabase.table('stock').select('*').eq('quincaillerie_id', q_id).eq('nom', nom).execute()
    existing = res.data or []

    if existing:
        nouveau_stock = existing[0]['quantite'] + quantite
        supabase.table('stock').update({
            'quantite': nouveau_stock,
            'prix_unitaire': prix,
            'seuil_alerte': seuil
        }).eq('id', existing[0]['id']).execute()
    else:
        supabase.table('stock').insert({
            'quincaillerie_id': q_id,
            'nom': nom,
            'quantite': quantite,
            'prix_unitaire': prix,
            'seuil_alerte': seuil
        }).execute()

    flash(f"Article '{nom}' enregistré.", "success")
    return redirect(url_for('index'))

@app.route('/modifier-produit/<int:id>', methods=['POST'])
def modifier_produit(id):
    supabase = get_supabase_client()
    q_id = session.get('quincaillerie_id')
    if not session.get('connecte') or not q_id or not supabase:
        return redirect(url_for('index'))

    nom = request.form.get('nom', '').strip()
    prix = float(request.form.get('prix', 0.0))
    stock = int(request.form.get('stock', 0))
    seuil = int(request.form.get('seuil', 5))

    supabase.table('stock').update({
        'nom': nom,
        'prix_unitaire': prix,
        'quantite': stock,
        'seuil_alerte': seuil
    }).eq('id', id).eq('quincaillerie_id', q_id).execute()

    flash("Produit mis à jour.", "success")
    return redirect(url_for('index'))

@app.route('/supprimer-produit/<int:id>')
def supprimer_produit(id):
    supabase = get_supabase_client()
    q_id = session.get('quincaillerie_id')
    if not session.get('connecte') or not q_id or not supabase:
        return redirect(url_for('index'))

    supabase.table('stock').delete().eq('id', id).eq('quincaillerie_id', q_id).execute()
    flash("Article supprimé du stock.", "info")
    return redirect(url_for('index'))

@app.route('/ajouter-vente', methods=['POST'])
def ajouter_vente():
    supabase = get_supabase_client()
    q_id = session.get('quincaillerie_id')
    if not session.get('connecte') or not q_id or not supabase:
        return redirect(url_for('index'))

    nom_produit = request.form.get('nom', '').strip()
    quantite = int(request.form.get('quantite', 0))
    date_vente = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))

    res = supabase.table('stock').select('*').eq('quincaillerie_id', q_id).eq('nom', nom_produit).execute()
    existing = res.data or []

    if not existing or existing[0]['quantite'] < quantite:
        flash("Stock insuffisant ou article inexistant.", "danger")
        return redirect(url_for('index'))

    produit = existing[0]
    supabase.table('stock').update({'quantite': produit['quantite'] - quantite}).eq('id', produit['id']).execute()
    supabase.table('ventes').insert({
        'quincaillerie_id': q_id,
        'nom_produit': nom_produit,
        'quantite_vendue': quantite,
        'prix_vente': produit['prix_unitaire'],
        'date_vente': date_vente,
        'vendu_par': session.get('nom_utilisateur')
    }).execute()

    flash("Vente enregistrée !", "success")
    return redirect(url_for('index'))

@app.route('/supprimer-vente/<int:id>')
def supprimer_vente(id):
    supabase = get_supabase_client()
    q_id = session.get('quincaillerie_id')
    if not session.get('connecte') or not q_id or not supabase:
        return redirect(url_for('index'))

    res = supabase.table('ventes').select('*').eq('id', id).eq('quincaillerie_id', q_id).execute()
    vente = res.data or []

    if vente:
        v = vente[0]
        res_prod = supabase.table('stock').select('*').eq('quincaillerie_id', q_id).eq('nom', v['nom_produit']).execute()
        prod = res_prod.data or []
        if prod:
            supabase.table('stock').update({'quantite': prod[0]['quantite'] + v['quantite_vendue']}).eq('id', prod[0]['id']).execute()

    supabase.table('ventes').delete().eq('id', id).eq('quincaillerie_id', q_id).execute()
    flash("Vente annulée et stock réajusté.", "info")
    return redirect(url_for('index'))

app = app