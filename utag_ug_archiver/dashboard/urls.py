from django.urls import path
from . import views
from .views.members_api import MembersDataTableAPIView
from .views.executives import ExecutiveBioUpdateView
app_name = 'dashboard'

urlpatterns =[
    path('',views.DashboardView.as_view(), name='dashboard'),
]

#For account management
urlpatterns += [
    path('account_management/admins',views.AdminListView.as_view(), name='admins'),
    path('account_management/admins/create',views.AdminCreateView.as_view(), name='create_admin'),
    path('account_management/user/update/',views.UserUpdateView.as_view(), name='update_user'),
    path('account_management/admins/upload',views.UploadAdminData.as_view(), name='upload_admins'),
    path('account_management/admin/delete/<int:admin_id>',views.AdminDeleteView.as_view(), name='delete_admin'),
    path('account_management/members/upload',views.UploadMemberData.as_view(), name='upload_members'),
    path('account_management/members/reference-csv',views.OrgReferenceCSVView.as_view(), name='members_reference_csv'),
    path('account_management/members/delete/<int:member_id>',views.MemberDeleteView.as_view(), name='delete_member'),
    path('account_management/members',views.MemberListView.as_view(), name='members'),
    path('account_management/members/api', MembersDataTableAPIView.as_view(), name='members_api'),
    path('account_management/members/create',views.MemberCreateView.as_view(), name='create_member'),
    path('account_management/member-search', views.MemberSearchView.as_view(), name='member_search'),
    path('account_management/check-staff-id/', views.CheckStaffIdView.as_view(), name='check_staff_id'),
]
#For executive management
urlpatterns += [
    path('executives/executive_members',views.ExecutiveMembersView.as_view(), name='executive_members'),
    path('executives/executive_members/print',views.PrintAllExecutivesView.as_view(), name='print_all_executives'),
    path('executives/executive_members/create/new_member',views.NewExecutiveMemberCreateView.as_view(), name='create_new_executive_member'),
    path('executives/executive_members/create/existing_member',views.ExistingExecutiveMemberCreateView.as_view(), name='create_existing_executive_member'),
    path('executives/executive_members/update/',views.UpdateExecutiveMemberView.as_view(), name='update_executive_member'),
    path('executives/executive_members/delete/<int:officer_id>',views.ExecutiveMemberDeleteView.as_view(), name='delete_executive_member'),
    # path('executives/committee_members',views.ExecutiveCommitteeMembersView.as_view(), name='committee_members'),
    # path('executives/committee_members/create/new',views.NewCommitteeMemberCreateView.as_view(), name='create_new_committee_member'),
    # path('executives/committee_members/create',views.ExecutiveCommitteeMemberCreateView.as_view(), name='create_existing_committee_member'),
    # path('executives/committee_members/update/',views.CommitteeMemberUpdateView.as_view(), name='update_committee_member'),
    # path('executives/committee_members/delete/<int:c_member_id>',views.CommitteeMemberDeleteView.as_view(), name='delete_committee_member'),
    path('executives/bio/edit/', ExecutiveBioUpdateView.as_view(), name='executive_bio_edit'),
]

#For event management
urlpatterns += [
    path('events',views.EventsView.as_view(), name='events'),
    path('events/create',views.EventCreateUpdateView.as_view(), name='create_event'),
    path('events/update/<int:event_id>',views.EventCreateUpdateView.as_view(), name='update_event'),
    path('events/delete/<int:event_id>',views.EventDeleteView.as_view(), name='delete_event'),
]

#For news management
urlpatterns += [
    path('news',views.NewsView.as_view(), name='news'),
    path('news/create',views.NewsCreateUpdateView.as_view(), name='create_news'),
    path('news/update/<int:news_id>',views.NewsCreateUpdateView.as_view(), name='update_news'),
    path('news/delete/<int:news_id>',views.NewsDeleteView.as_view(), name='delete_news'),
]

# For gallery management
urlpatterns += [
    path('galleries/', views.GalleryListView.as_view(), name='gallery'),
    path('galleries/add/', views.GalleryCreateView.as_view(), name='gallery_add'),
    path('galleries/upload-images/', views.ImageUploadView.as_view(), name='gallery_upload_images'),
    path('galleries/delete/<int:gallery_id>/', views.DeleteGalleryView.as_view(), name='gallery_delete'),
    path('galleries/edit/<int:gallery_id>/', views.EditGalleryView.as_view(), name='gallery_edit'),
    path('galleries/view/<int:gallery_id>/', views.ViewGalleryDetails.as_view(), name='gallery_view'),
    path('images/delete/<int:image_id>/', views.DeleteImageView.as_view(), name='image_delete'),
]

#For Document management
urlpatterns += [
    path('documents/',views.DocumentsView.as_view(), name='documents'),
    path('documents/create',views.DocumentCreateUpdateView.as_view(), name='create_document'),
    path('documents/update/<int:document_id>',views.DocumentCreateUpdateView.as_view(), name='update_document'),
    path('documents/delete_file/',views.DeleteFileView.as_view(), name='delete_file'),
    path('documents/delete/<int:document_id>',views.DeleteDocumentView.as_view(), name='delete_document'),
   
]

#For Announcement management
urlpatterns += [
    path('announcements',views.AnnouncementsView.as_view(), name='announcements'),
    path('announcements/create',views.AnnouncementCreateUpdateView.as_view(), name='create_announcement'),
    path('announcements/update/<int:announcement_id>',views.AnnouncementCreateUpdateView.as_view(), name='update_announcement'),
    path('announcements/delete/<int:announcement_id>',views.AnnouncementDeleteView.as_view(), name='delete_announcement'),
]

# For Notifications
urlpatterns += [
    path('notifications', views.NotificationsView.as_view(), name='notifications'),
    path('notifications/delete/<int:notification_id>', views.NotificationDeleteView.as_view(), name='delete_notification'),
    path('notifications/read/<int:notification_id>', views.NotificationReadView.as_view(), name='read_notification'),
    path('notifications/notification_details/<int:notification_id>/', views.NotificationDetailsView.as_view(), name='notification_details'),
]

#For Adverts
urlpatterns +={
    path('adverts',views.AdvertsView.as_view(), name='adverts'),
    path('adverts/create',views.AdvertCreateView.as_view(), name='create_advert'),
    path('adverts/update/',views.AdvertUpdateView.as_view(), name='update_advert'),
    path('adverts/delete/<int:advert_id>',views.AdvertDeleteView.as_view(), name='delete_advert'),
    path('adverts/orders', views.AdvertOrdersView.as_view(), name='advert_orders'),
    path('plans',views.PlansView.as_view(), name='plans'),
    path('plans/create', views.AdvertPlanCreateView.as_view(), name='create_plan'),
    path('plans/update', views.AdvertPlanUpdateView.as_view(), name='update_plan'),
    path('plans/delete/<int:plan_id>', views.AdvertPlanDeleteView.as_view(), name='delete_plan'),
    # Advert plan and company management removed; keep adverts CRUD routes only
}

#For User Profile management
urlpatterns += [
    path('profile',views.ProfileView.as_view(), name='profile'),
    path('profile/update_profile_pic',views.ChangeProfilePicView.as_view(), name='update_profile_pic'),
]

# Carousel Slider
urlpatterns += [
    path('carousel/', views.CarouselSlideListView.as_view(), name='carousel_slide_list'),
    path('carousel/create/', views.CarouselSlideCreateUpdateView.as_view(), name='carousel_slide_create'),
    path('carousel/update/<int:slide_id>/', views.CarouselSlideCreateUpdateView.as_view(), name='carousel_slide_update'),
    path('carousel/delete/<int:slide_id>/', views.CarouselSlideDeleteView.as_view(), name='carousel_slide_delete'),
]