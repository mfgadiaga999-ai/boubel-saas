import os
from collections import Counter
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client
from datetime import datetime

app = Flask(__name__, template_folder='templates', static_folder='../public/static')
app.secret_key = os.environ.get('SECRET_KEY', 'boubel_saas_secret_key_2026')
if __name__ == '__main__':
    app.run(debug=True)

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

@app.route('/demo')
def mode_demo():
    # Données fictives pour la démonstration
    info_quincaillerie = {
        "nom_entreprise": "Quincaillerie Mouhidine (DÉMO)"
    }
    
    produits_demo = [
        {"id": 1, "nom_affichage": "Ciment SOCOCIM 50kg", "prix_unitaire": 4500, "stock_total": 45, "seuil_alerte": 10},
        {"id": 2, "nom_affichage": "Fer à béton 10mm", "prix_unitaire": 3800, "stock_total": 8, "seuil_alerte": 10}, # Alerte
        {"id": 3, "nom_affichage": "Peinture BLANCOLOR 20L", "prix_unitaire": 18500, "stock_total": 12, "seuil_alerte": 5},
        {"id": 4, "nom_affichage": "Pointe 80mm (Kg)", "prix_unitaire": 1000, "stock_total": 3, "seuil_alerte": 5} # Alerte
    ]
    
    ventes_demo = [
        {"id": 1, "date_vente": "14/08/2026 14:30", "nom_produit": "Ciment SOCOCIM 50kg", "quantite_vendue": 5, "prix_vente": 4500, "vendu_par": "Moussa"},
        {"id": 2, "date_vente": "14/08/2026 11:15", "nom_produit": "Peinture BLANCOLOR 20L", "quantite_vendue": 1, "prix_vente": 18500, "vendu_par": "Fatou"}
    ]
    
    insights_demo = [
        {"bg": "danger", "icon": "fa-triangle-exclamation", "badge": "Urgent", "titre": "Stock Critique", "message": "Le <b>Fer à béton 10mm</b> est passé sous le seuil critique (8 restants)."},
        {"bg": "success", "icon": "fa-chart-line", "badge": "Tendance", "titre": "Meilleure Vente", "message": "Le <b>Ciment SOCOCIM</b> représente 60% de vos ventes aujourd'hui."}
    ]

    # Calcul des KPI fictifs
    ca_demo = sum(v["prix_vente"] * v["quantite_vendue"] for v in ventes_demo)
    valeur_stock = sum(p["prix_unitaire"] * p["stock_total"] for p in produits_demo)
    alertes_count = sum(1 for p in produits_demo if p["stock_total"] <= p["seuil_alerte"])

    return render_template(
        'index.html',
        is_demo=True,
        info_quincaillerie=info_quincaillerie,
        produits=produits_demo,
        ventes=ventes_demo,
        gerant_insights=insights_demo,
        ca_quincaillerie=ca_demo,
        valeur_stock_totale=valeur_stock,
        alertes_count=alertes_count
    )

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

    # Définition du mois en cours (Format AAA-MM, ex: '2026-03')
    mois_courant = datetime.now().strftime('%Y-%m')

    if session.get('connecte') and supabase:
        role = session.get('role')
        q_id = session.get('quincaillerie_id')

        # --- ESPACE SUPER ADMIN ---
        if role == 'super_admin':
            res_q = supabase.table('quincailleries').select('*').order('id').execute()
            liste_quincailleries = res_q.data or []

            res_v = supabase.table('ventes').select('*').execute()
            toutes_les_ventes = res_v.data or []

            res_s = supabase.table('stock').select('*').execute()
            tout_le_stock = res_s.data or []

            res_u = supabase.table('utilisateurs').select('id, quincaillerie_id, identifiant').eq('role', 'gerant').execute()
            users_map = {u['quincaillerie_id']: u['identifiant'] for u in (res_u.data or []) if u.get('quincaillerie_id')}

            ca_total_global_mois = 0.0
            total_ventes_count_mois = 0
            total_articles_stock = sum(int(item.get('quantite', 0)) for item in tout_le_stock)

            stats_q = {q['id']: {'ca': 0.0, 'nb_ventes': 0, 'nb_produits': 0} for q in liste_quincailleries}

            for v in toutes_les_ventes:
                qid = v.get('quincaillerie_id')
                date_v = str(v.get('date_vente', ''))
                
                # Vérifier si la vente appartient au mois en cours
                if date_v.startswith(mois_courant):
                    montant = float(v.get('prix_vente', 0)) * int(v.get('quantite_vendue', 1))
                    ca_total_global_mois += montant
                    total_ventes_count_mois += 1
                    
                    if qid in stats_q:
                        stats_q[qid]['ca'] += montant
                        stats_q[qid]['nb_ventes'] += 1

            for s in tout_le_stock:
                qid = s.get('quincaillerie_id')
                if qid in stats_q:
                    stats_q[qid]['nb_produits'] += 1

            for q in liste_quincailleries:
                qid = q['id']
                q['identifiant_gerant'] = users_map.get(qid, 'Non attribué')
                q['ca'] = stats_q.get(qid, {}).get('ca', 0.0)
                q['nb_ventes'] = stats_q.get(qid, {}).get('nb_ventes', 0)
                q['nb_produits'] = stats_q.get(qid, {}).get('nb_produits', 0)

            insights = []
            nb_clients = len(liste_quincailleries)

            if nb_clients > 0:
                ca_moyen = ca_total_global_mois / nb_clients

                top_q = max(liste_quincailleries, key=lambda x: x['ca'], default=None)
                if top_q and top_q['ca'] > 0:
                    insights.append({
                        'badge': 'Leader du mois',
                        'bg': 'success',
                        'icon': 'fa-trophy',
                        'titre': 'Quincaillerie en Tête ce Mois-ci',
                        'message': f"<b>{top_q['nom_entreprise']}</b> mène ce mois avec <b>{top_q['ca']:,.0f} FCFA</b> de CA ({top_q['nb_ventes']} ventes)."
                    })

                inactives = [q for q in liste_quincailleries if q['ca'] == 0]
                if inactives:
                    noms_inactives = ", ".join([q['nom_entreprise'] for q in inactives[:3]])
                    insights.append({
                        'badge': 'Inactivité',
                        'bg': 'warning',
                        'icon': 'fa-triangle-exclamation',
                        'titre': 'Pas encore de Ventes ce Mois-ci',
                        'message': f"<b>{len(inactives)} quincaillerie(s)</b> n'ont pas encore enregistré de ventes ce mois-ci ({noms_inactives})."
                    })

                ventes_du_mois = [v.get('nom_produit') for v in toutes_les_ventes if str(v.get('date_vente', '')).startswith(mois_courant)]
                if ventes_du_mois:
                    top_prod_nom, top_prod_count = Counter(ventes_du_mois).most_common(1)[0]
                    insights.append({
                        'badge': 'Tendance',
                        'bg': 'primary',
                        'icon': 'fa-fire',
                        'titre': 'Produit Star du Mois',
                        'message': f"Article le plus vendu sur le réseau ce mois : <b>{top_prod_nom}</b> ({top_prod_count} ventes)."
                    })

                insights.append({
                    'badge': 'Moyenne',
                    'bg': 'info',
                    'icon': 'fa-chart-line',
                    'titre': 'Chiffre d\'Affaires Moyen du Mois',
                    'message': f"Moyenne mensuelle du réseau : <b>{ca_moyen:,.0f} FCFA</b> par point de vente."
                })

            return render_template(
                'super_admin.html',
                quincailleries=liste_quincailleries,
                total_clients=nb_clients,
                ca_total_global=ca_total_global_mois,
                total_ventes_count=total_ventes_count_mois,
                total_articles_stock=total_articles_stock,
                insights=insights
            )

        # --- ESPACE GERANT DE QUINCAILLERIE ---
        elif q_id:
            res_q = supabase.table('quincailleries').select('*').eq('id', q_id).execute()
            if res_q.data:
                info_quincaillerie = res_q.data[0]
                if not info_quincaillerie.get('actif'):
                    session.clear()
                    flash("Votre compte est suspendu. Veuillez contacter l'administrateur.", "danger")
                    return redirect(url_for('index'))

            # Stock de la quincaillerie
            res_stock = supabase.table('stock').select('*').eq('quincaillerie_id', q_id).order('nom').execute()
            valeur_stock_totale = 0.0
            
            for item in (res_stock.data or []):
                stk = item.get('quantite', 0)
                seuil = item.get('seuil_alerte', 5)
                prix_u = float(item.get('prix_unitaire', 0))
                valeur_stock_totale += (stk * prix_u)
                
                if stk <= seuil:
                    alertes_count += 1
                produits.append({
                    'id': item.get('id'),
                    'nom_affichage': item.get('nom'),
                    'stock_total': stk,
                    'prix_unitaire': prix_u,
                    'seuil_alerte': seuil
                })

            # Ventes de la quincaillerie
            res_ventes = supabase.table('ventes').select('*').eq('quincaillerie_id', q_id).order('created_at', desc=True).execute()
            ca_quincaillerie_mois = 0.0
            ventes_du_mois_gerant = []
            
            for v in (res_ventes.data or []):
                qte = int(v.get('quantite_vendue', 1))
                px = float(v.get('prix_vente', 0))
                date_v = str(v.get('date_vente', ''))

                # Si la vente date du mois en cours
                if date_v.startswith(mois_courant):
                    ca_quincaillerie_mois += (qte * px)
                    ventes_du_mois_gerant.append(v.get('nom_produit'))

                ventes.append({
                    'id': v.get('id'),
                    'date_vente': date_v,
                    'nom_produit': v.get('nom_produit'),
                    'quantite_vendue': qte,
                    'prix_vente': px,
                    'vendu_par': v.get('vendu_par')
                })

            # Insights Gérant pour le mois en cours
            gerant_insights = []

            if ventes_du_mois_gerant:
                top_p_nom, top_p_cnt = Counter(ventes_du_mois_gerant).most_common(1)[0]
                gerant_insights.append({
                    'badge': 'Top Vente du Mois',
                    'bg': 'success',
                    'icon': 'fa-star',
                    'titre': 'Votre produit phare ce mois-ci',
                    'message': f"L'article <b>{top_p_nom}</b> est votre meilleure vente du mois avec <b>{top_p_cnt} transaction(s)</b>."
                })

            if alertes_count > 0:
                gerant_insights.append({
                    'badge': 'Attention',
                    'bg': 'danger',
                    'icon': 'fa-box-open',
                    'titre': 'Réapprovisionnement requis',
                    'message': f"Vous avez <b>{alertes_count} article(s)</b> proche(s) de la rupture."
                })
            else:
                gerant_insights.append({
                    'badge': 'Optimal',
                    'bg': 'info',
                    'icon': 'fa-check-circle',
                    'titre': 'Niveau de Stock Sain',
                    'message': "Tous vos produits sont bien approvisionnés."
                })

            gerant_insights.append({
                'badge': 'Mensuel',
                'bg': 'primary',
                'icon': 'fa-calendar-check',
                'titre': 'Chiffre d\'Affaires Mensuel',
                'message': f"Vous avez réalisé <b>{ca_quincaillerie_mois:,.0f} FCFA</b> de CA durant le mois en cours."
            })

            return render_template(
                'index.html',
                produits=produits,
                ventes=ventes,
                alertes_count=alertes_count,
                info_quincaillerie=info_quincaillerie,
                ca_quincaillerie=ca_quincaillerie_mois,
                valeur_stock_totale=valeur_stock_totale,
                gerant_insights=gerant_insights
            )

    return render_template(
        'index.html',
        produits=produits,
        ventes=ventes,
        alertes_count=alertes_count,
        info_quincaillerie=info_quincaillerie,
        ca_quincaillerie=0,
        valeur_stock_totale=0,
        gerant_insights=[]
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

# --- ACTIONS ESPACE SUPER ADMIN ---

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

# --- ACTIONS ESPACE QUINCAILLERIE (GERANT) ---

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