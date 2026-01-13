# 📋 Production Deployment Checklist

## Pre-Deployment (Development)

- [ ] **Verify Installation**
  - [ ] Pillow installed: `pip list | grep Pillow`
  - [ ] All new files present in workspace
  - [ ] No import errors: `python manage.py check`

- [ ] **Test Image Upload**
  - [ ] Upload a large image (5MB) to admin
  - [ ] Verify it's compressed (check file size)
  - [ ] Verify image quality is acceptable
  - [ ] Check media folder size reduced

- [ ] **Test Lazy Loading**
  - [ ] Open website in browser
  - [ ] Open DevTools (F12)
  - [ ] Go to Network tab, filter by "img"
  - [ ] Scroll page and verify images load as you scroll
  - [ ] Initial images loaded should be less than total

- [ ] **Run Test Suite**
  - [ ] `python manage.py test`
  - [ ] All tests pass
  - [ ] No new warnings or errors

- [ ] **Test Template Tags**
  - [ ] Create test page with `{% lazy_img %}`
  - [ ] Verify HTML renders correctly
  - [ ] Check lazy loading works
  - [ ] Test in multiple browsers

## Staging Environment

- [ ] **Deploy Code**
  - [ ] Push to staging branch
  - [ ] Deploy all new files
  - [ ] Run migrations (if any): `python manage.py migrate`
  - [ ] Collect static files: `python manage.py collectstatic`

- [ ] **Optimize Existing Images** (One-time)
  - [ ] Backup media folder: `cp -r media media.backup`
  - [ ] Run command: `python manage.py optimize_images`
  - [ ] Monitor progress and check logs
  - [ ] Verify optimized images loaded correctly
  - [ ] Check total media folder size reduced (should be 85-95%)

- [ ] **Update Settings**
  - [ ] Add image optimization config to settings
  - [ ] Set environment variables (if needed)
  - [ ] Verify AUTO_OPTIMIZE_IMAGES=true

- [ ] **Update Base Template**
  - [ ] Add CSS: `<link rel="stylesheet" href="{% static 'dashboard/css/image-optimization.css' %}">`
  - [ ] Add JS: `<script src="{% static 'dashboard/js/lazy-load.js' %}"></script>`
  - [ ] Test page loads and styles work

- [ ] **Browser Testing**
  - [ ] Chrome: Test lazy loading
  - [ ] Firefox: Test lazy loading
  - [ ] Safari: Test lazy loading
  - [ ] Mobile Safari: Test on iPhone
  - [ ] Android Chrome: Test on Android phone
  - [ ] Edge: Test lazy loading
  - [ ] All images render correctly
  - [ ] No console errors

- [ ] **Performance Testing**
  - [ ] Run Google PageSpeed: https://pagespeed.web.dev
  - [ ] Check Mobile score (should be 80+)
  - [ ] Check Desktop score (should be 90+)
  - [ ] Core Web Vitals improved
  - [ ] LCP < 2.5s
  - [ ] FID < 100ms
  - [ ] CLS < 0.1

- [ ] **Load Testing**
  - [ ] Simulate high traffic
  - [ ] Monitor memory usage
  - [ ] Check CPU utilization
  - [ ] Verify no file access errors
  - [ ] Check response times

- [ ] **Functionality Testing**
  - [ ] Test user profile pictures load
  - [ ] Test executive photos display correctly
  - [ ] Test event images show properly
  - [ ] Test news featured images work
  - [ ] Test gallery images load correctly
  - [ ] Test advertisement images display

- [ ] **Content Review**
  - [ ] Review image quality
  - [ ] Check for visual artifacts
  - [ ] Verify colors are accurate
  - [ ] Test dark/light themes work

## Production Deployment

- [ ] **Pre-Deployment Backup**
  - [ ] Backup database: `pg_dump ... > backup.sql`
  - [ ] Backup media folder: `tar -czf media-backup.tar.gz media/`
  - [ ] Store backups securely
  - [ ] Test backup restoration

- [ ] **Deploy Code**
  - [ ] Code review completed
  - [ ] All tests pass
  - [ ] Zero known issues
  - [ ] Deploy during maintenance window if possible

- [ ] **Production Setup**
  - [ ] Copy new files to production
  - [ ] Update settings.py with production values
  - [ ] Set environment variables:
    - [ ] `AUTO_OPTIMIZE_IMAGES=true`
    - [ ] `IMAGE_JPEG_QUALITY=85`
  - [ ] Verify permissions: `chmod 755 media/`

- [ ] **Collect Static Files** (Critical!)
  - [ ] Run: `python manage.py collectstatic --noinput`
  - [ ] Verify CSS/JS files in staticfiles folder
  - [ ] Check nginx/apache can serve them
  - [ ] Clear CDN cache if using CDN

- [ ] **Optimize Existing Images** (One-time, ~30 min)
  - [ ] Run: `python manage.py optimize_images`
  - [ ] Monitor progress (check logs)
  - [ ] Expected to take 5-30 minutes
  - [ ] Verify media folder size (should be 85-95% smaller)
  - [ ] Do NOT interrupt this process

- [ ] **Verify Web Server Configuration**
  - [ ] Nginx configured correctly
  - [ ] Cache headers set for images
  - [ ] Gzip compression enabled
  - [ ] Static files served efficiently
  - [ ] Media files accessible

- [ ] **Test Production Site**
  - [ ] Access main domain
  - [ ] Test all pages load
  - [ ] Check images display correctly
  - [ ] Open DevTools and verify lazy loading
  - [ ] Scroll pages and verify images load
  - [ ] Test on mobile device
  - [ ] Check console for errors

- [ ] **Performance Verification**
  - [ ] Run Google PageSpeed on production domain
  - [ ] Verify scores improved significantly
  - [ ] Check Core Web Vitals
  - [ ] Monitor page load times
  - [ ] Check server resource usage

- [ ] **Monitor for Issues** (First 24 hours)
  - [ ] Watch error logs: `tail -f /var/log/django.log`
  - [ ] Monitor CPU/Memory/Disk usage
  - [ ] Check web server logs
  - [ ] Monitor user reports/feedback
  - [ ] Check image loading quality

- [ ] **Database Verification**
  - [ ] Images accessible in database
  - [ ] No orphaned records
  - [ ] Backup completed successfully
  - [ ] Database performance normal

## Post-Deployment

- [ ] **Documentation**
  - [ ] Update team documentation
  - [ ] Document any custom configurations
  - [ ] Share deployment notes
  - [ ] Record performance baseline

- [ ] **Team Communication**
  - [ ] Notify team of deployment
  - [ ] Share performance improvements
  - [ ] Explain new template tags
  - [ ] Provide training if needed

- [ ] **Update Template Library** (Gradual)
  - [ ] Identify all image tags in templates
  - [ ] Create list of files to update
  - [ ] Update high-traffic pages first
  - [ ] Test each update thoroughly
  - [ ] Document template tag usage

- [ ] **Monitoring Setup**
  - [ ] Set up PageSpeed monitoring
  - [ ] Create performance dashboards
  - [ ] Set up alerts for slowdowns
  - [ ] Schedule weekly performance reviews

- [ ] **Customer Notification** (Optional)
  - [ ] Announce faster website
  - [ ] Share performance improvements
  - [ ] Thank users for patience
  - [ ] Provide feedback channel

## Rollback Plan (If Issues)

If you need to rollback (unlikely):

```bash
# 1. Restore database backup
psql ... < backup.sql

# 2. Restore media folder
tar -xzf media-backup.tar.gz

# 3. Revert code to previous version
git checkout previous-commit

# 4. Restart services
systemctl restart gunicorn
systemctl restart nginx

# 5. Verify site works
# Visit production domain and test
```

## Success Criteria

✅ **Deployment is successful when:**
- [ ] No errors in logs
- [ ] All images load correctly
- [ ] Lazy loading works (verified in DevTools)
- [ ] PageSpeed scores improved 30+ points
- [ ] Core Web Vitals all green
- [ ] Page load time reduced 70-80%
- [ ] Users report faster experience
- [ ] No increase in CPU/Memory usage
- [ ] Database integrity verified
- [ ] All functionality works

## Performance Baselines (Record These)

**Before Optimization:**
- Home page load time: ___ seconds
- PageSpeed Mobile score: ___ 
- PageSpeed Desktop score: ___
- Average image size: ___ KB
- Total media folder: ___ GB

**After Optimization:**
- Home page load time: ___ seconds (target: 70% improvement)
- PageSpeed Mobile score: ___ (target: +30 points)
- PageSpeed Desktop score: ___ (target: +30 points)
- Average image size: ___ KB (target: 85% reduction)
- Total media folder: ___ GB (target: 85% reduction)

**Improvement Achieved:**
- Load time improvement: ___% ✓
- PageSpeed improvement: ___% ✓
- Image size reduction: ___% ✓

## Troubleshooting During Deployment

| Issue | Solution |
|-------|----------|
| Images still large | Verify optimize_images command ran |
| Lazy loading not working | Check CSS/JS included in base template |
| Images blurry | Increase IMAGE_JPEG_QUALITY in settings |
| Import errors | Verify all files deployed correctly |
| Performance not improved | Check PageSpeed again, clear cache |
| Errors in logs | Check file permissions, disk space |

## Sign-Off

- [ ] **Developer**: Code tested and verified ___________
- [ ] **QA**: Testing completed and approved ___________
- [ ] **DevOps**: Infrastructure ready ___________
- [ ] **Deployment**: Successful deployment confirmed ___________
- [ ] **Verification**: Production verified working ___________

---

**Deployment Date**: _______________  
**Deployed By**: _______________  
**Notes**: _______________

---

**See Also:**
- Complete guide: `IMAGE_OPTIMIZATION.md`
- Quick start: `QUICK_START_IMAGE_OPTIMIZATION.md`
- Implementation summary: `PERFORMANCE_OPTIMIZATION_SUMMARY.md`
