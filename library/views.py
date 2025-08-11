from datetime import timedelta

from django.db.models import Q, F
from django.db.models.aggregates import Count
from rest_framework import viewsets, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer, ExtendLoanSerializer
from rest_framework.decorators import action
from django.utils import timezone
from .tasks import send_loan_notification

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.select_related("author").all()
    serializer_class = BookSerializer
    pagination_class = PageNumberPagination

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    @action(detail=False, methods=['get'], url_path="top-active")
    def top_active(self, request, **kwargs):
        members = Member.objects.values(
            member_id=F("id"),
            username=F("user__username"),
            email=F("user__username")
        ).annotate(
            no_of_active_loans=Count("loans", distinct=True, filter=Q(is_returned=False))
        ).order_by("-no_of_active_loans")[:5]

        return Response({'data': members}, status=status.HTTP_200_OK)

class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = ExtendLoanSerializer

    @action(detail=True, methods=['post'])
    def extend_due_date(self, request, **kwargs):
        loan = self.get_object()
        additional_days = int(request.data.get('additional_days'))

        if loan.due_date >= timezone.now():
            return Response({'error': 'Loan is already overdue.'}, status=status.HTTP_400_BAD_REQUEST)

        loan.due_date = loan.due_date + timedelta(days=additional_days)
        loan.save()

        return Response({'error': 'Loan due date updated.'}, status=status.HTTP_200_OK)


