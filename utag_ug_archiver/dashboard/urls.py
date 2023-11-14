from django.urls import path
from . import views
app_name = 'dashboard'
urlpatterns = [
    path('',views.DashboardView.as_view(), name='dashboard'),
    path('account_management/admins',views.AdminListView.as_view(), name='admins'),
    path('account_management/admins/create_update',views.AdminCreateUpdateView.as_view(), name='create_update_admin'),
    path('account_management/admins/upload',views.UploadAdminData.as_view(), name='upload_admins'),
    path('account_management/admin/delete/<int:admin_id>',views.AdminDeleteView.as_view(), name='delete_admin'),
    path('account_management/members/upload',views.UploadMemberData.as_view(), name='upload_members'),
    path('account_management/members/delete/<int:member_id>',views.MemberDeleteView.as_view(), name='delete_member'),
    path('account_management/members',views.MemberListView.as_view(), name='members'),
    path('account_management/members/create_update',views.MemberCreateUpdateView.as_view(), name='create_update_member'),
    path('executives/officers',views.ExecutiveOfficersView.as_view(), name='officers'),
    path('account_management/officers/delete/<int:officer_id>',views.OfficerDeleteView.as_view(), name='delete_officer'),
    path('executives/committee_members',views.ExecutiveCommitteeMembersView.as_view(), name='committee_members'),
    path('account_management/committee_members/delete/<int:c_member_id>',views.CommitteeMemberDeleteView.as_view(), name='delete_committee_member'),
    path('documents/internal',views.InternalDocumentsView.as_view(), name='internal_documents'),
    path('documents/external',views.ExternalDocumentsView.as_view(), name='external_documents'),
    path('events',views.EventsView.as_view(), name='events'),
    path('events/create',views.EventCreateView.as_view(), name='create_event'),
    path('events/update/<int:event_id>',views.EventUpdateView.as_view(), name='update_event'),
    path('events/delete/<int:event_id>',views.EventDeleteView.as_view(), name='delete_event'),
    path('news',views.NewsView.as_view(), name='news'),
    path('profile',views.ProfileView.as_view(), name='profile'),
    path('profile/update_profile_pic',views.ChangeProfilePicView.as_view(), name='update_profile_pic'),
]