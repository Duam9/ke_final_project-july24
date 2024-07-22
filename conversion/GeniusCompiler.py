import config.genius_config as config
import pprint
import re
from googletrans import Translator
import requests

from lyricsgenius import Genius

class GeniusCompiler:
    def __init__(self):
        self.genius = Genius(config.ACCESS_TOKEN)
        self.header_pattern = re.compile(r'\[(.*?)\]')


    def __clean_lyrics(self, lyrics):
        lyrics_cleaned = re.sub(r'You might also like(?=\[)', '\n', lyrics) # Remove "You might also like" followed by a '['
        lyrics_cleaned = re.sub(r'(?<!\n)\[', '\n[', lyrics_cleaned)        # Ensure there is a newline before any '['
        lyrics_cleaned = re.sub(r'\n+', '\n', lyrics_cleaned)               # Reduce consecutive newlines to a single newline

        return lyrics_cleaned.strip()
    

    def get_lyrics(self, title, artist):
        """Scraped lyrics from a song using its title and primary artist name

        Args:
            title (str): song's title
            artist (str): artist's name

        Returns:
            dict: cleaned lyrics of the song.
        """
        song = self.genius.search_song(title, artist)

        if song:
            # Clean lyrics to remove "You might also like" issue
            lyrics = self.__clean_lyrics(song.lyrics)
            
            print(f"Lyrics scraped successfully")
        else:
            print(f"Lyrics for '{title}' by {artist} not found.")
            lyrics = False

        return lyrics
    

    def search_song(self, title, artist):
        return self.genius.search_song(title, artist)
        

    def get_song_metadata(self, song_id):
        """Get song's metadata by its Genius ID

        Args:
            song_id (str): ID of the song

        Returns:
            dict: metadata of the requested song
        """
        song_url = f'{config.BASE_URL}/songs/{song_id}'
        data = requests.get(song_url, headers=config.HEADERS).json()
        song_data = data['response']['song']
        
        writer_artists = [artist['name'] for artist in song_data['writer_artists']] if song_data['writer_artists'] else [song_data['primary_artist']['name']]

        metadata = {
            'genius_id': song_id,
            'title': song_data['title'],
            'artist': song_data['primary_artist']['name'],
            'language': song_data['language'],
            'writer_artists': writer_artists
        }
        return metadata


    def translate_to_english(self, text):
        translator = Translator()
        translated = translator.translate(text, dest='en')
        return translated.text.title()  # Convert to title format for uniformity

    def split_by_section(self, lyrics, artist, verbose=False):
        """Splits the provided lyrics in sections using the information present on it.

        Args:
            lyrics (str): lyrics scraped from Genius
            artist (str): primary artist name (case when the artist is not mentioned on the scraped information)
            verbose (bool, optional): whether to display some information of the process. Defaults to False.

        Returns:
            dict: lyrics splitted by sections
        """

        # List of standard section names
        standard_sections = ['Intro', 'Verse', 'Pre-Chorus', 'Chorus', 'Post-Chorus', 'Bridge', 'Outro']

       # Split the lyrics based on the headers
        genius_paragraphs = {}
        lines = lyrics.splitlines()

        current_paragraph_name = None
        current_paragraph_content = []
        
        header_count = {}

        # Variables to store the last content of specific sections
        last_chorus_content = ''
        last_pre_chorus_content = ''
        last_post_chorus_content = ''

        pre_chorus = 0
        chorus = 0
        post_chorus = 0
        i = 0

        while i < len(lines):
            line = lines[i]
            match = self.header_pattern.match(line.strip())
            if match:
                # Save the previous paragraph if exists
                if current_paragraph_name and current_paragraph_content:
                    genius_paragraphs[current_paragraph_name] = {
                        'content': ' '.join(current_paragraph_content),
                        'singer': singer_names
                    }

                    # Store the last content of specific sections
                    if "Chorus" in current_paragraph_name and chorus == 0 :
                        last_chorus_content = ' '.join(current_paragraph_content)
                        chorus = 1
                    elif "Pre-Chorus" in current_paragraph_name and pre_chorus == 0 :
                        last_pre_chorus_content = ' '.join(current_paragraph_content)
                        pre_chorus = 1
                    elif "Post-Chorus" in current_paragraph_name and post_chorus == 0:
                        last_post_chorus_content = ' '.join(current_paragraph_content)
                        post_chorus = 1
                    
                # Extract paragraph name and singer(s) if provided
                header_info = match.group(1).strip()
                if ':' in header_info:
                    header_parts = header_info.split(':')
                    paragraph_name = header_parts[0].strip()
                    singer_names = [name.strip() for name in header_parts[1].split('&')]
                else:
                    paragraph_name = header_info
                    singer_names = [artist]  # Default to original artist if no singer specified
                
                # Preserve numeric suffix if present
                numeric_suffix_match = re.search(r'\d+$', paragraph_name)
                numeric_suffix = numeric_suffix_match.group() if numeric_suffix_match else ''
                paragraph_name_base = paragraph_name[:numeric_suffix_match.start()].strip() if numeric_suffix_match else paragraph_name

                # Translate paragraph name to English
                paragraph_name_base = self.translate_to_english(paragraph_name_base)

                # Ensure paragraph name matches standard sections
                original_paragraph_name = paragraph_name_base
                paragraph_name_base = next((section for section in standard_sections if section in paragraph_name_base), paragraph_name_base)

                # Combine base name and numeric suffix, if any
                paragraph_name = f"{paragraph_name_base.title()} {numeric_suffix}".strip()

                # Print a message if paragraph name is not part of standard sections
                if paragraph_name_base.lower() not in (section.lower() for section in standard_sections):
                    print(f"Warning: Paragraph name '{original_paragraph_name}' is not a standard section name.")

                # Check the next line to see if it's content or another section header
                next_line = lines[i + 1] if i + 1 < len(lines) else ''
                next_match = self.header_pattern.match(next_line.strip())

                if paragraph_name_base in ["Chorus", "Pre-Chorus", "Post-Chorus"] and (not next_line.strip() or next_match):
                    # Append last content if the next line is empty or another header
                    if paragraph_name_base == "Chorus" and last_chorus_content:
                        current_paragraph_content = []
                        current_paragraph_content.append(last_chorus_content)
                    elif paragraph_name_base == "Pre-Chorus" and last_pre_chorus_content:
                        current_paragraph_content = []
                        current_paragraph_content.append(last_pre_chorus_content)
                    elif paragraph_name_base == "Post-Chorus" and last_post_chorus_content:
                        current_paragraph_content = []
                        current_paragraph_content.append(last_post_chorus_content)
                else:
                    current_paragraph_content = []

                # Adjust paragraph name if it's a duplicate
                if paragraph_name in header_count:
                    header_count[paragraph_name] += 1
                    paragraph_name = f"{paragraph_name.split()[0]} {header_count[paragraph_name]}"
                else:
                    header_count[paragraph_name] = 1

                current_paragraph_name = paragraph_name
            else:
                current_paragraph_content.append(line)
            
            i += 1

        # Save the last paragraph
        if current_paragraph_name and current_paragraph_content:
            genius_paragraphs[current_paragraph_name] = {
                'content': ' '.join(current_paragraph_content),
                'singer': singer_names
            }

        # Print extracted paragraphs to check
        if genius_paragraphs and verbose:
            for name, content_info in genius_paragraphs.items():
                print(f"Paragraph Name: {name}")
                print(f"Content: {content_info['content']}")
                print(f"Singer(s): {', '.join(content_info['singer'])}")
                print("------")
        elif not(genius_paragraphs):
            print("The provided lyrics do not contain information about sections")
            genius_paragraphs = False

        return genius_paragraphs
        

if __name__ == '__main__':
    
    title = 'Blinding Lights'
    artist = 'The Weeknd'

    # Create an instance of our compiler and scrape the lyrics from Genius
    compiler = GeniusCompiler()
    lyrics = compiler.get_lyrics(title, artist)
    paragraphs = compiler.split_by_section(lyrics, artist, verbose=True)

    pprint.pprint(type(lyrics))