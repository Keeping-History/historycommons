import glob
import os
from multiprocessing import Pool

from bs4 import BeautifulSoup
from mongoengine import *
import spacy
from date_spacy import find_dates


def dprint(msg: str):
    if os.environ.get('APP_DEBUG'):
        print(msg)


connection_params = {
    "username": os.environ.get('MONGODB_USER'),
    "password": os.environ.get('MONGODB_PASS'),
    "authentication_source": os.environ.get('MONGODB_AUTHDB'),
    "host": os.environ.get('MONGODB_HOST'),
    "port": int(os.environ.get('MONGODB_PORT'))
}

dprint(f"Connecting to DB {os.environ.get('MONGODB_NAME')} with options {connection_params}")
connect(os.environ.get('MONGODB_NAME'), **connection_params)

nlp = spacy.blank('en')

# Add the component to the pipeline
nlp.add_pipe('find_dates')


class Citation(Document):
    link = StringField(required=True)
    title = StringField(required=True)
    full_text = StringField()


class Entity(Document):
    name = StringField(required=True)
    title = StringField()


class EntryImage(Document):
    link = StringField()
    caption = StringField(required=True)
    source = StringField()


class Entry(Document):
    title = StringField(required=True)
    timeline_tags = ListField(ReferenceField(Entity))
    entity_tags = ListField(ReferenceField(Entity))
    citations = ListField(ReferenceField(Citation))
    content = StringField(required=True)
    image = ReferenceField(EntryImage, required=False)
    date = DateField(required=False)


def process_file(idx: int, file: str):
    dprint('Processing file #{}: {}'.format(idx, file))

    f = open(file, "r")
    soup = BeautifulSoup(f.read(), "html.parser")
    timelines = soup.find_all(id='timelineEntries')
    if len(timelines) == 0:
        dprint('No timeline entries found in file #{}: {}'.format(idx, file))
        return
    else:
        dprint('Found a timeline in file #{}: {}'.format(idx, file))

        entries = timelines[0].find_all('div', {"class": "i"})
        dprint('Processing {} timeline entries in file #{}: {}'.format(len(entries), idx, file))
        for entry_idx, entry in enumerate(entries):

            title = entry.find('div', {"class": "iT"}).find('h2').text.strip()

            doc = nlp(title)
            date = None
            for ent in doc.ents:
                if ent.label_ == "DATE":
                    date = ent._.date

            if len(Entry.objects(title=title)) > 0:
                dprint('Already found timeline entry {} of {} with title: {}'.format(entry_idx, len(entries), title))
                pass

            dprint('Processing timeline entry {} of {} with title: {}'.format(entry_idx, len(entries), title))

            tag_groups = entry.find('div', {"class": "t"}).find_all('p')
            dprint('Got tag groups for entry {} of {}: {}'.format(entry_idx, len(entries), tag_groups))

            entity_tags = []
            timeline_tags = []
            citations = []
            entry_image = None

            content = entry.find('p')
            dprint('Got tag content for entry {} of {}: {}'.format(entry_idx, len(entries), content))

            def entity_title_split(s: str):
                return s.split("=", 1)[1].split('.', 1)[0]

            for tag_group in tag_groups:
                if tag_group.find('b'):
                    if 'Timeline' in tag_group.find('b').text:
                        for tag in tag_group.find_all('a'):
                            dprint('Creating Timeline tag for entry {} of {}: {}'.format(entry_idx, len(entries), tag.text))
                            timeline_tags.append(
                                Entity.objects(title=tag.text).upsert_one(
                                    name=entity_title_split(tag['href']),
                                    title=tag.text
                                ))

                    elif 'Entity' in tag_group.find('b').text:
                        for tag in tag_group.find_all('a'):
                            dprint('Creating Entity tag for entry {} of {}: {}'.format(entry_idx, len(entries), tag.text))
                            entity_tags.append(
                                Entity.objects(title=tag.text).upsert_one(
                                    name=entity_title_split(tag['href']),
                                    title=tag.text
                                ))

            for cite in content.find_all('cite'):
                for l in cite.find_all('a'):
                    if l.text:
                        dprint('Creating Citation for entry {} of {}: {}'.format(entry_idx, len(entries), l.text))
                        citations.append(
                            Citation.objects(title=l.text).upsert_one(
                                link=l.get('href', ''),
                                full_text=l.get('onmouseover').split("return OL('", 1)[1].split("')", 1)[0] if l.get(
                                    'onmouseover') else "",
                            ))

            for photo in content.find_all('span', {"class": "tmlnImg"}):
                source_text = ""
                if len(photo.text.split("[Source: ", 1)) > 1:
                    source_text = photo.text.split("[Source: ", 1)[1].split("]", 1)[0].strip()
                    dprint('Creating Entity Photo for entry {} of {}: {}'.format(entry_idx, len(entries), photo.text))

                entry_image = EntryImage.objects(link=photo.find_all('img')[0].attrs['src']).upsert_one(
                    caption=photo.text.split("[Source: ", 1)[0].strip(),
                    source=source_text,
                )

            dprint('Creating Entity {} of {}: {}'.format(entry_idx, len(entries), title))

            Entry.objects(title=title).upsert_one(
                timeline_tags=timeline_tags,
                entity_tags=entity_tags,
                citations=citations,
                content=str(content),
                image=entry_image,
                date=date
            )
            dprint('Created Entity {} of {}: {}'.format(entry_idx, len(entries), title))

    dprint('Finished Processing file #{}: {}'.format(idx, file))


if __name__ == '__main__':
    files = list(glob.glob('../data/**/*.html'))
    dprint('Total number of files: {}'.format(len(files)))

    with Pool() as p:
        p.starmap(process_file, enumerate(files))
