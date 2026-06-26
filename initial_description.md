# description
I want to create an application with web interface to send email marketing. 
# dependencies
django
django rest framework
celery
redis
google-auth
jinja2
postgres/pgbinary
google-api-python-client

# workflows

-user will go to the homepage, which shows all current existing "accounts" (which is google account to be able to send the email)/ and campaigns (with statuses)
- user can add a new account (by click to a link to add account) or use existing added account
    + user add an account, which the app looks at the `credentials.json` and tries to ask for permission to send email(env.py SCOPES), once user logged in and redirect back, 
save credential (token.json) into the database (using google-auth)
    + user use existing account, then the app will check if the token in the database is expired or not, if it expired, try to refresh, if failed to do so mark it as broken
- once use used an account to send the email, show a form that contains: campaign name, subject (jinja2 template), label (used to label all the email that to be sent during the campaign), contacts (a csv file - template is `RRContacts.csv`), template (text field, jinja2 template) and a submit button
- when user click submit, validate the subject and template if all variables existed (variables must only support: `first_name`)
- when validated is done, create a new campaign subject and add all the contacts into the contacts table. Add a celery task so that we can track the progress of the campaign
- the celery process then, listen to new task and send the email accordingly