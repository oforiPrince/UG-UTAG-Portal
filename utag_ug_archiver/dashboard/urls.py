from django.urls import path
from . import views
app_name = 'dashboard'

urlpatterns =[
    path('',views.DashboardView.as_view(), name='dashboard'),
]

#For account management
urlpatterns += [
    path('account_management/admins',views.AdminListView.as_view(), name='admins'),
    path('account_management/admins/create',views.AdminCreateView.as_view(), name='create_admin'),
    path('account_management/admins/update/',views.AdminUpdateView.as_view(), name='update_admin'),
    path('account_management/admins/upload',views.UploadAdminData.as_view(), name='upload_admins'),
    path('account_management/admin/delete/<int:admin_id>',views.AdminDeleteView.as_view(), name='delete_admin'),
    path('account_management/members/upload',views.UploadMemberData.as_view(), name='upload_members'),
    path('account_management/members/delete/<int:member_id>',views.MemberDeleteView.as_view(), name='delete_member'),
    path('account_management/members',views.MemberListView.as_view(), name='members'),
    path('account_management/members/create',views.MemberCreateView.as_view(), name='create_member'),
    path('account_management/members/update/',views.MemberUpdateView.as_view(), name='update_member'),
]
#For executive management
urlpatterns += [
    path('executives/officers',views.ExecutiveOfficersView.as_view(), name='officers'),
    path('executives/officers/create/new_member',views.NewOfficerCreateView.as_view(), name='create_new_officer'),
    path('executives/officers/create/existing_member',views.ExistingExecutiveOfficerCreateView.as_view(), name='create_existing_officer'),
    path('executives/officers/update/',views.UpdateExecutiveOfficerView.as_view(), name='update_officer'),
    path('executives/officers/delete/<int:officer_id>',views.OfficerDeleteView.as_view(), name='delete_officer'),
    path('executives/committee_members',views.ExecutiveCommitteeMembersView.as_view(), name='committee_members'),
    path('executives/committee_members/create/new',views.NewCommitteeMemberCreateView.as_view(), name='create_new_committee_member'),
    path('executives/committee_members/create',views.ExecutiveCommitteeMemberCreateView.as_view(), name='create_existing_committee_member'),
    path('executives/committee_members/update/',views.CommitteeMemberUpdateView.as_view(), name='update_committee_member'),
    path('executives/committee_members/delete/<int:c_member_id>',views.CommitteeMemberDeleteView.as_view(), name='delete_committee_member'),
]

#For event management
urlpatterns += [
    path('events',views.EventsView.as_view(), name='events'),
    path('events/create',views.EventCreateView.as_view(), name='create_event'),
    path('events/update/',views.EventUpdateView.as_view(), name='update_event'),
    path('events/delete/<int:event_id>',views.EventDeleteView.as_view(), name='delete_event'),
]

#For news management
urlpatterns += [
    path('news',views.NewsView.as_view(), name='news'),
    path('news/create',views.NewsCreateView.as_view(), name='create_news'),
    path('news/update/',views.NewsUpdateView.as_view(), name='update_news'),
    path('news/delete/<int:news_id>',views.NewsDeleteView.as_view(), name='delete_news'),
]

#For Document management
urlpatterns += [
    path('documents/internal',views.InternalDocumentsView.as_view(), name='internal_documents'),
    path('documents/external',views.ExternalDocumentsView.as_view(), name='external_documents'),
    path('documents/internal/add',views.AddInternalDocumentView.as_view(), name='add_internal_document'),
    path('documents/update/',views.UpdateFileView.as_view(), name='update_file'),
    path('documents/external/add',views.AddExternalDocumentView.as_view(), name='add_external_document'),
    path('documents/delete_file/',views.DeleteFileView.as_view(), name='delete_file'),
   
]

#For Announcement management
urlpatterns += [
    path('announcements',views.AnnouncementsView.as_view(), name='announcements'),
    path('announcements/create',views.AnnouncementCreateView.as_view(), name='create_announcement'),
    path('announcements/update/',views.AnnouncementUpdateView.as_view(), name='update_announcement'),
    path('announcements/delete/<int:announcement_id>',views.AnnouncementDeleteView.as_view(), name='delete_announcement'),
]

#For Adverts
urlpatterns +={
    path('adverts',views.AdvertsView.as_view(), name='adverts'),
    path('adverts/create',views.AdvertCreateView.as_view(), name='create_advert'),
    path('adverts/update/',views.AdvertUpdateView.as_view(), name='update_advert'),
    path('adverts/delete/<int:advert_id>',views.AdvertDeleteView.as_view(), name='delete_advert'),
    path('plans',views.AdvertPlansView.as_view(), name='plans'),
    path('plans/create',views.AdvertPlanCreateView.as_view(), name='create_plan'),
    path('plans/update/',views.AdvertPlanUpdateView.as_view(), name='update_plan'),
    path('plans/delete/<int:plan_id>',views.AdvertPlanDeleteView.as_view(), name='delete_plan'),
    path('companies',views.CompaniesView.as_view(), name='companies'),
    path('companies/create',views.CompanyCreateView.as_view(), name='create_company'),
    path('companies/update/',views.CompanyUpdateView.as_view(), name='update_company'),
    path('companies/delete/<int:company_id>',views.CompanyDeleteView.as_view(), name='delete_company'),
}

#For User Profile management
urlpatterns += [
    path('profile',views.ProfileView.as_view(), name='profile'),
    path('profile/update_profile_pic',views.ChangeProfilePicView.as_view(), name='update_profile_pic'),
]