/**
 * Native Lazy Load Image System
 * Supports data-src for lazy loading and image optimization
 * Fallback to Intersection Observer for older browsers
 */

(function() {
    'use strict';

    // Configuration
    const config = {
        // Placeholder image (low quality/small size)
        placeholderSrc: '/static/dashboard/assets/images/placeholder.png',
        
        // Distance in pixels to load before image enters viewport
        rootMargin: '50px',
        
        // For browsers without Intersection Observer
        loadingClass: 'lazyload-loading',
        loadedClass: 'lazyload-loaded',
        errorClass: 'lazyload-error',
    };

    /**
     * Initialize lazy image loading with Intersection Observer
     */
    function initLazyLoading() {
        // Check if Intersection Observer is supported
        if (!('IntersectionObserver' in window)) {
            // Fallback: load all images immediately
            loadAllImages();
            return;
        }

        // Create observer with configuration
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    loadImage(img);
                    observer.unobserve(img);
                }
            });
        }, {
            rootMargin: config.rootMargin,
        });

        // Observe all lazy-loadable images
        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });

        // Also watch for dynamically added images
        if ('MutationObserver' in window) {
            const mutationObserver = new MutationObserver((mutations) => {
                mutations.forEach(mutation => {
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === 1) { // Element node
                            node.querySelectorAll('img[data-src]').forEach(img => {
                                imageObserver.observe(img);
                            });
                        }
                    });
                });
            });

            mutationObserver.observe(document.body, {
                childList: true,
                subtree: true,
            });
        }
    }

    /**
     * Load a single image
     */
    function loadImage(img) {
        if (!img.dataset.src) return;

        const src = img.dataset.src;
        
        // Create a new image to preload
        const newImg = new Image();
        
        newImg.onload = () => {
            // Update the img element
            img.src = src;
            img.removeAttribute('data-src');
            img.classList.add(config.loadedClass);
            img.classList.remove(config.loadingClass);
            
            // Trigger loaded event
            img.dispatchEvent(new Event('lazyload'));
        };
        
        newImg.onerror = () => {
            img.classList.add(config.errorClass);
            img.classList.remove(config.loadingClass);
            
            // Dispatch error event
            img.dispatchEvent(new Event('lazyloaderror'));
        };
        
        img.classList.add(config.loadingClass);
        newImg.src = src;
    }

    /**
     * Fallback: Load all images without lazy loading
     */
    function loadAllImages() {
        document.querySelectorAll('img[data-src]').forEach(img => {
            loadImage(img);
        });
    }

    /**
     * Force load all remaining lazy images
     * (useful before print or page transitions)
     */
    window.lazyLoadAll = function() {
        document.querySelectorAll('img[data-src]').forEach(img => {
            loadImage(img);
        });
    };

    /**
     * Manual load function for specific image
     */
    window.lazyLoadImage = function(img) {
        if (typeof img === 'string') {
            img = document.querySelector(img);
        }
        if (img && img.dataset.src) {
            loadImage(img);
        }
    };

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLazyLoading);
    } else {
        initLazyLoading();
    }
})();

/**
 * Image optimization strategies:
 * 
 * 1. BROWSER NATIVE LAZY LOADING (primary)
 *    - Uses HTML5 loading="lazy" attribute
 *    - No JavaScript needed
 *    - Works in modern browsers (Chrome, Firefox, Edge, Safari 15.1+)
 *
 * 2. INTERSECTION OBSERVER API (fallback)
 *    - Loads images when they're about to enter viewport
 *    - Reduces initial page load and saves bandwidth
 *    - Smooth user experience
 *
 * 3. COMPRESSION & RESIZING (automatic)
 *    - Pillow optimizes all images on upload
 *    - JPEG quality set to 85 (good balance)
 *    - Images resized to appropriate dimensions
 *    - Maximum file size enforced
 *
 * 4. RESPONSIVE IMAGES (recommended future improvement)
 *    - Serve different sizes for different devices
 *    - Use srcset and sizes attributes
 *    - Save bandwidth on mobile
 *
 * Usage:
 * {% load image_tags %}
 * {% lazy_img event.featured_image.url "Event" "img-fluid rounded" %}
 * 
 * Or use the tag directly:
 * <img data-src="/path/to/image.jpg" 
 *      src="/static/placeholder.png"
 *      loading="lazy"
 *      alt="Description"
 *      class="img-fluid lazyload">
 */
