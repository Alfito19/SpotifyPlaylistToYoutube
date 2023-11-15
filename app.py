from flask import Flask, redirect, request, session, url_for, render_template
from spotipy.oauth2 import SpotifyOAuth
from spotipy import Spotify
from google_auth_oauthlib.flow import InstalledAppFlow
from oauthlib.oauth2.rfc6749.errors import InsecureTransportError, InvalidGrantError
from keys import keys
import os
import json
# ID playlist spotify: 1rhzlhUjjIHYejHbxWen7y
# ID playlist yt: PLEwHLZE4ev9aXUvQgsMqupOfPUpq-O-Ix
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "keys/youtube_key.json"

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configuración para Spotify
sp_oauth = SpotifyOAuth(
    client_id=keys.spotify_client_id,
    client_secret=keys.spotify_client_secret,
    redirect_uri="http://127.0.0.1:5000/callback",
    scope="playlist-modify-private playlist-read-private"
)

# Configuración para YouTube
flow = InstalledAppFlow.from_client_secrets_file('keys/youtube_key.json',
    scopes=['https://www.googleapis.com/auth/youtube',
            'https://www.googleapis.com/auth/youtube.readonly',
            'https://www.googleapis.com/auth/youtube.force-ssl']
)
flow.run_local_server()

yt_session = flow.authorized_session()

def get_spotify_playlist_tracks(playlist_id, access_token):
    sp = Spotify(auth=access_token)
    playlist_tracks = sp.playlist_tracks(playlist_id)
    return playlist_tracks

# Función para buscar canciones en YouTube
def search_youtube_song(youtube, query):
    request = youtube.search().list(
        q=query,
        part='id',
        type='video',
        maxResults=1
    )
    response = request.execute()
    if 'items' in response:
        return response['items'][0]['id']['videoId']
    return None

# Función para agregar canción a la playlist de YouTube
def add_song_to_playlist(youtube, playlist_id, video_id):
    request = youtube.playlistItems().insert(
        part='snippet',
        body={
            'snippet': {
                'playlistId': playlist_id,
                'resourceId': {
                    'kind': 'youtube#video',
                    'videoId': video_id
                }
            }
        }
    )
    request.execute()

@app.route('/', methods=['GET', 'POST'])
def home():
    playlist_tracks = []

    if request.method == 'POST':
        spotify_playlist_id = request.form['spotify_playlist']
        youtube_playlist_id = request.form['youtube_playlist']
        session['spotify_playlist_id'] = spotify_playlist_id
        yt_session['youtube_playlist_id'] = youtube_playlist_id

        # Obtener información de la playlist desde Spotify
        access_token_spotify = session.get('access_token_spotify')
        if access_token_spotify:
            playlist_tracks = get_spotify_playlist_tracks(spotify_playlist_id, access_token_spotify)
            print(f'Token de acceso de Spotify: {access_token_spotify}')
            
            # Verificar si hay un token de acceso de YouTube en la sesión
            access_token_youtube = session.get('access_token_youtube')
            if not access_token_youtube:
                print("not youtube")
                # Si no hay token de acceso de YouTube, redirigir a la autenticación de YouTube
                
                return redirect(url_for('youtube_auth'))

            # Inicializar el servicio de YouTube
            credentials = flow.credentials

            # Iterar sobre las canciones y buscarlas en YouTube
            for track in playlist_tracks:
                song_name = track['track']['name']
                artist_name = track['track']['artists'][0]['name']  # Tomamos solo el primer artista
                query = f"{song_name} {artist_name}"

                # Buscar la canción en YouTube
                video_id = search_youtube_song(flow, query)
                if video_id:
                    # Agregar la canción a la playlist de YouTube
                    add_song_to_playlist(flow, youtube_playlist_id, video_id)
                    print(song_name + " added")
                else:
                    print(song_name + " not added")

    return render_template('home.html', playlist_tracks=playlist_tracks)

@app.route('/spotify-auth')
def spotify_auth():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/youtube-auth')
def youtube_auth():
    try:
        if 'youtube_code' in session:
            youtube_code = session['youtube_code']
            print("Authorization Code: ok")

            auth_url= flow.authorization_url(prompt='consent')

            authorization_url = f"https://127.0.0.1:5000/youtube-auth?code={youtube_code}"
            print("Authorization URL: ok")
            flow.fetch_token(code=authorization_url)
            # session = flow.authorized_session()
            session.pop('youtube_code')

            return 'Autenticación de YouTube exitosa.'
        else:
            return 'Error en la autenticación de YouTube.'
    except InsecureTransportError:
        return 'Error: La autenticación de YouTube requiere una conexión segura (HTTPS).'
    except InvalidGrantError as e:
        print(f"Error al obtener el token de acceso de YouTube: {e}")
        return 'Error al obtener el token de acceso de YouTube.'
    except Exception as e:
        return f'Error: {str(e)}'

@app.route('/callback')
def callback():
    # Manejar la respuesta de Spotify
    if request.args.get('code'):
        token_info = sp_oauth.get_access_token(request.args['code'])
        access_token_spotify = token_info['access_token']
        # Usa access_token_spotify para hacer solicitudes a la API de Spotify

    # Manejar la respuesta de YouTube
    if 'code' in request.args:
        session['youtube_code'] = request.args['code']
        return redirect(url_for('youtube_auth'))

    return 'Autenticación exitosa. Puedes cerrar esta ventana.'


@app.route('/clear-session')
def clear_session():
    session.clear()
    return 'Sesión limpia. Puedes intentar el proceso de autenticación nuevamente.'

if __name__ == '__main__':
    app.run(debug=True)

