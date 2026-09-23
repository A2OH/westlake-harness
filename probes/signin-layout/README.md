# Sign-in layout white-box probe

Rebuilds the McDonald's sign-in sheet in code with the same view classes and drawing paths its
layout uses (`fragment_login_registration_child.xml`): a scroll view over nested `LinearLayout`s,
`TextView`s with typefaces loaded from assets (the `McDTextView` path; McDonald's two font files, taken
from its APK at build time), underlined link text, gradient-bordered button rows with an `ImageView`.

After the first draw it checks that every view measured to a non-zero size, that both typefaces
loaded, that the header laid out, and that drawing the root into a bitmap produced non-background
pixels. The pass marker is:

```text
[WL-SIGNIN-LAYOUT] verdict=PASS_SIGNIN_LAYOUT_DRAWN views=N zeroSized=0 ...
```

It exercises rendering of that screen without Realm, Firebase or the fraud SDKs in the way. It
does not exercise McDonald's own resources or fragments; that stays for the app launch itself.
Build with `MCDONALDS_APK=<path to base.apk> ./build.sh`; the fonts are McDonald's and are not
kept in this repository.
