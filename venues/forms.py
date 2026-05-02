from django import forms
from .models import BookingRequest

class BookingRequestForm(forms.ModelForm):
    class Meta:
        model = BookingRequest
        fields = ['name', 'phone', 'email', 'event_date', 'participants_count', 'event_format', 'comment']
        
    def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)
       for field in self.fields:
           self.fields[field].widget.attrs.update({'class': 'form-control'})