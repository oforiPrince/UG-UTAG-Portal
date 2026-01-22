/**
 * UTAG UG Portal - Custom JavaScript
 * Lazy loading and performance optimizations
 */

document.addEventListener('DOMContentLoaded', function() {
  // Lazy load images with intersection observer for better performance
  const lazyImages = document.querySelectorAll('img[loading="lazy"]');
  
  if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver(function(entries, observer) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          const img = entry.target;
          img.classList.add('loaded');
          observer.unobserve(img);
        }
      });
    });
    
    lazyImages.forEach(function(img) {
      imageObserver.observe(img);
    });
  } else {
    // Fallback for older browsers
    lazyImages.forEach(function(img) {
      img.classList.add('loaded');
    });
  }

  // Executives section scroll navigation
  const scrollContainer = document.querySelector('.utag-executives-scroll');
  const prevBtn = document.querySelector('.utag-scroll-prev');
  const nextBtn = document.querySelector('.utag-scroll-next');
  
  if (scrollContainer && prevBtn && nextBtn) {
    const scrollAmount = 350; // Card width + gap
    
    // Update arrow states based on scroll position
    function updateArrowStates() {
      const maxScroll = scrollContainer.scrollWidth - scrollContainer.clientWidth;
      prevBtn.classList.toggle('disabled', scrollContainer.scrollLeft <= 0);
      nextBtn.classList.toggle('disabled', scrollContainer.scrollLeft >= maxScroll - 5);
    }
    
    // Scroll left
    prevBtn.addEventListener('click', function() {
      scrollContainer.scrollBy({ left: -scrollAmount, behavior: 'smooth' });
    });
    
    // Scroll right
    nextBtn.addEventListener('click', function() {
      scrollContainer.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    });
    
    // Update states on scroll
    scrollContainer.addEventListener('scroll', updateArrowStates);
    
    // Initial state
    updateArrowStates();
    
    // Update on window resize
    window.addEventListener('resize', updateArrowStates);
  }
});
