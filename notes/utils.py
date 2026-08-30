def cloudinary_attachment_url(url):
    """
    Given a Cloudinary delivery URL, return a version that forces a download
    (Content-Disposition: attachment) instead of opening inline in the browser.
    Cloudinary supports this via the `fl_attachment` delivery flag.
    """
    if url and '/upload/' in url and 'fl_attachment' not in url:
        return url.replace('/upload/', '/upload/fl_attachment/', 1)
    return url
