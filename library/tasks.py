from typing import List

from celery import shared_task
from django.db.models import Exists, OuterRef, Q, QuerySet, F, Value
from django.db.models.functions import Concat
from django.template.defaultfilters import pluralize

from .models import Loan, Member, Book
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title

        app_send_email(
            'Book Loaned Successfully',
            f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            member_email
        )
    except Loan.DoesNotExist:
        pass

@shared_task
def check_overdue_loans_task():
    today = timezone.now().date()
    overdue_qs = Q(is_returned=False, due_date__lt=today)
    members = Member.objects.filter(Exists(Loan.objects.filter(member_id=OuterRef("id")))).filter(overdue_qs).annotate(
        email=F("user__email"),
        username=F("user__username")
    )

    # iterate fetching 100 members at a time
    for member in members.iterator(100):
        # get the books directly
        books = Book.objects.filter(loans__member=member, loans__is_returned=False, loans__due_date__lt=today).values(
            "title", author_name=Concat(F("author__first_name"), Value(" "), F("author__last_name"))
        )
        notify_member_of_overdue_books(member, books)


def notify_member_of_overdue_books(member, books):
    email = member.email
    username = member.username

    noun = "book"
    count = len(books)

    if count > 1:
        noun = pluralize(noun)

    books_table = ""

    for index, book in enumerate(books):
        books_table += "{}. {} by {}\n".format(index + 1, book.get("title"), book.get("author_name"))

    app_send_email(
        'You have {} {} overdue'.format(count, noun),
        'Hello {},\n\nYou have the following loaned {} overdue. Kindly return today.\n\n{}'.format(username, noun, books_table),
        email
    )



def app_send_email(subject, message, *email_recipients):
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=list(email_recipients),
        fail_silently=False,
    )