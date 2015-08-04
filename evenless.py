# coding: utf-8

import operator
from collections import defaultdict
import email
from email.header import decode_header
import codecs
import math

import notmuch


COUNT_THRESHHOLD = 3
PADDING = 0.000001


def get_tokens(msg):
    """split an email into tokens

    :type msg: email.message
    """
    tokens = list()

    for header in ['From', 'To', 'Cc', 'Subject', 'Date', 'User-Agent']:
        if msg[header] is not None:
            tokens += [decode_header(msg[header])[0][0]]

    for part, charset in zip(msg.walk(), msg.get_charsets()):
        try:
            codecs.lookup(charset)
        except (LookupError, TypeError):
            charset = 'ascii'

        if part.get_content_type() not in ['text/plain', 'text/html']:
            continue
        else:
            payload = part.get_payload(decode=True).decode(charset, 'ignore')  # TODO fix broken html encodings
            tokens += payload.split()
    return tokens


def clean_tokens(tokens):
    return [token.strip('.,:!?)(') for token in tokens]


def tokens_and_count(tag):
    words = defaultdict(int)
    mail_number = 0

    db = notmuch.Database()
    query = db.create_query('tag:{}'.format(tag))
    messages = query.search_messages()

    for message in messages:
        mail_number += 1

        filename = message.get_filename()
        msg = email.message_from_file(file(filename))

        tokens = get_tokens(msg)
        tokens = clean_tokens(tokens)
        for token in tokens:
            words[token] += 1
    return words, mail_number


def word_spam_prob(word):
    total_occurrence = spam_words[word] + ham_words[word]
    if total_occurrence < COUNT_THRESHHOLD:
        spamprob = 0.5
    else:
        spamprob = 1.0 * spam_words[word] / total_occurrence

    # correction a la wikipedia
    spamprob = (1.5 + total_occurrence * spamprob) / (COUNT_THRESHHOLD + total_occurrence)
    return spamprob


def tokens_spam_prob(tokens):
    probs = [word_spam_prob(token) for token in tokens]
    probs = [prob for prob in probs if prob is not None]

    eta = sum([math.log(1 - prob + PADDING) - math.log(prob + PADDING) for prob in probs])
    eta = min(100, eta)
    prob = 1.0 / (1 + math.exp(eta))
    return prob

spam_words, spam_mails = tokens_and_count('spam')
ham_words, ham_mails = tokens_and_count('ham')

#sorted(ham_words.items(), key=operator.itemgetter(1), reverse=True)
#sorted(spam_words.items(), key=operator.itemgetter(1), reverse=True)


def get_test_mails():
    db = notmuch.Database()
    query = db.create_query('tag:unread AND tag:inbox')
    messages = query.search_messages()
    for message in messages:
        filename = message.get_filename()
        msg = email.message_from_file(file(filename))
        tokens = get_tokens(msg)
        tokens = clean_tokens(tokens)

        yield decode_header(msg['Subject'])[0][0], tokens_spam_prob(tokens)

for subject, spam_prob in get_test_mails():
    print('{}: {}'.format(subject, spam_prob))
