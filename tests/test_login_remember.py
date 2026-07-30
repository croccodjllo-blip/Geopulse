from __future__ import annotations


def test_login_form_has_remember_me():
    from app import LoginForm, app

    with app.test_request_context("/login"):
        form = LoginForm()
        assert "remember_me" in form._fields
        assert bool(form.remember_me.default) is False
